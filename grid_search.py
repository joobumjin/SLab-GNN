import argparse
from tqdm import tqdm

import math
import os

import matplotlib.pyplot as plt
import pickle
import torch
from torch.nn import MSELoss
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from GNN.src.gnn_modular import Modular_GCN
from GNN.src import test_acc


def parse_args(args=None):
    """ 
    Perform command-line argument parsing (other otherwise parse arguments with defaults). 
    To parse in an interative context (i.e. in notebook), add required arguments.
    These will go into args and will generate a list that can be passed in.
    For example: 
        parse_args('--type', 'rnn', ...)
    """
    parser = argparse.ArgumentParser(description="Specify Hyperparameters for Grid Searching the hyperparameters of the GNN", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--data',           required=True,              help='File path to the assignment data file.')
    parser.add_argument('--pred',           required=True,              choices=['TER', 'VEGF', 'Both'],    help='Type of Value being Predicted from QBAMs')
    parser.add_argument('--chkpt_path',     default='',                 help='where the model checkpoint is')
    parser.add_argument('--img_path',       default='',                 help='where the model saves loss graphs')
    parser.add_argument('--batch_size',     type=int,   default=20,     help='Model\'s batch size.')

    if args is None: 
        return parser.parse_args()      ## For calling through command line
    return parser.parse_args(args)      ## For calling through notebook.


def train(model, train_loader, optimizer, criterion):
    model.train()
    # for data in tqdm(train_loader, desc="Training", leave=False):
    for data in train_loader:
        data = data.to(model.device)  # Move data to the same device as the model
        out = model(data)
        loss = criterion(out, data.y)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

def test(model, loader, criterion, print_met=False):
    model.eval()
    total_loss = 0.0
    with torch.no_grad():
        for data in tqdm(loader, desc="Testing", leave=False):
            data = data.to(model.device)
            out = model(data)
            loss = criterion(out, data.y)
            total_loss += loss.item()

            if print_met:
                print(f"Predicted: {out}, True: {data.y}, RMSE: {math.sqrt(loss.item())}")

    avg_loss = total_loss / len(loader.dataset)
    return math.sqrt(avg_loss)

def train_model(train_loader, val_loader, test_loader, model, output_filepath, img_path, learning_rate, num_epochs, num_gcn, num_dense, convergence_epsilon = 1):

    best_rmse = 99999999999
    prev_rmse = None

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print("Using,", device)
    model = model.to(device)
    model.device = device
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = MSELoss()

    train_losses = []
    val_losses = []

    for epoch in tqdm(range(1, num_epochs + 1), desc="Training Epochs"):
        train(model, train_loader, optimizer, criterion)
        train_rmse = test(model, train_loader, criterion, False)
        # val_rmse = test(model, val_loader, criterion, False)
        val_rmse = test(model, test_loader, criterion, False)

        train_losses.append(train_rmse)
        val_losses.append(val_rmse)

        if prev_rmse and math.abs(train_rmse - prev_rmse) < convergence_epsilon: break

        prev_rmse = train_rmse

        if epoch % 20 == 0:
          print(f'\nEpoch: {epoch:03d}, Train RMSE: {train_rmse:.4f}, Val RMSE: {val_rmse:.4f}\n')

    torch.save(model.state_dict(), output_filepath)
    print("Saved the model to:", output_filepath)

    plt.figure(figsize=(10, 6))
    plt.plot(train_losses, label='Training RMSE')
    plt.plot(val_losses, label='Validation RMSE')
    plt.xlabel('Epoch')
    plt.ylabel('RMSE')
    plt.title('Training and Validation RMSE')
    plt.legend()
    plt.savefig(f"{img_path}/RMSE_e{num_epochs}_lr{learning_rate}_g{num_gcn}_d{num_dense}.jpg")
    plt.close()


def check_for_nan(dataset):
    for i, data in enumerate(dataset):
        if torch.isnan(data.x).any():
            print(f"NaN found in features at index {i}")
        if torch.isnan(data.y).any():
            print(f"NaN found in target at index {i}")

def load_dataset_from_pickle(pickle_file):
    with open(pickle_file, 'rb') as f:
        dataset = pickle.load(f)
    if isinstance(dataset, list) and all(isinstance(d, Data) for d in dataset):
        return dataset
    else:
        raise ValueError("The loaded dataset is not a list of Data objects).")

def main(args):
    data_dirs = {}
    for data_type in ['TER', 'VEGF', 'Both']:
        data_dirs[f"Train_{data_type}"] = f"{args.data}/{data_type}/Train_{data_type}.pkl"
        data_dirs[f"Test_{data_type}"] = f"{args.data}/{data_type}/Test_{data_type}.pkl"

    target = args.pred #when validating TER, check the really small values
    #the model might end up predicting the exact same TER value for all smaller values
    train_pickle_file = data_dirs[f"Train_{target}"]
    test_pickle_file = data_dirs[f"Test_{target}"]

    dataset = load_dataset_from_pickle(train_pickle_file)

    train_index = int(len(dataset) * 0.95)
    train_dataset = dataset[:train_index]
    val_dataset = dataset[train_index:]

    test_dataset = load_dataset_from_pickle(test_pickle_file)
    test_loader = DataLoader(test_dataset)

    check_for_nan(train_dataset)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)


    num_features = train_dataset[0].x.shape[1]  # Number of features per node
    num_targets = train_dataset[0].y.shape[0]


    print("###################################")
    print()
    print(f'Number of training graphs: {len(train_dataset)}')
    print(f'Number of test graphs: {len(val_dataset)}')
    print(f'Number of features: {num_features}')
    print(f'Number of targets: {num_targets}')
    print("###################################")

    # data = dataset[0]
    # print()
    # print(data)
    # print('=============================================================')
    # print(f'Number of nodes: {data.num_nodes}')
    # print(f'Number of edges: {data.num_edges}')
    # print(f'Average node degree: {data.num_edges / data.num_nodes:.2f}')
    # print(f'Has isolated nodes: {data.has_isolated_nodes()}')
    # print(f'Has self-loops: {data.has_self_loops()}')
    # print(f'Is undirected: {data.is_undirected()}')
    # print('=============================================================')
    # print()
    # print(f'Number of training graphs: {len(train_dataset)}')
    # print(f'Number of test graphs: {len(val_dataset)}')
    # print('=============================================================')
    # print()
    # # for step, data in enumerate(train_loader):
    # #     print(f'Step {step + 1}:')
    # #     print('=======')
    # #     print(f'Number of graphs in the current batch: {data.num_graphs}')
    # #     print(data)
    # #     print()
    # print()
    # exit()

    # lr_epoch = [(0.0001, 500), (0.0005, 300), (0.001, 150), (0.003, 150), (0.005, 100)]
    lr_epoch = [(0.00001, 500), (0.00005, 500), (0.0001, 500), (0.0005, 500)]


    for (learning_rate, num_epochs) in lr_epoch:
    #   for num_gcn in ([2, 3, 4, 5]):
    #     for num_dense in ([2, 3, 4, 5, 6]):
      for num_gcn in ([2, 3, 4, 5]):
        for num_dense in ([2, 3, 4, 5, 6]):
    
            print("___________________________________")
            print()
            print("Learning Rate:", learning_rate)
            print("Epochs:", num_epochs )
            print(f"Num GCN Layers {num_gcn}")
            print(f"Num Dense Layers {num_dense}")
            print("___________________________________")

            output_filepath = f'{args.chkpt_path}/{args.pred}_Abs_model_e{num_epochs}_lr{learning_rate}_g{num_gcn}_d{num_dense}.pth'

            model = Modular_GCN(num_features, num_targets, num_dense = num_dense, num_gcn = num_gcn)
            train_model(train_loader, val_loader, test_loader, model, output_filepath, args.img_path, learning_rate, num_epochs, num_gcn, num_dense)

            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

            model = Modular_GCN(num_features, num_targets, num_dense = num_dense, num_gcn = num_gcn)
            model.load_state_dict(torch.load(output_filepath, map_location=torch.device(device)))

            test_acc.test_model(test_loader, model)

## END UTILITY METHODS
##############################################################################

if __name__ == '__main__':
    main(parse_args())