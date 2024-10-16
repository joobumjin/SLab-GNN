import argparse
from tqdm import tqdm

import math
import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import pickle
import torch
from torch.nn import CrossEntropyLoss
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from GNN.src.gnn_modular import Modular_GCN
import GNN.src.gnn_multiple as GCNs


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
    parser.add_argument('--pred',           required=True,              choices=['Donor'],    help='Type of Value being Predicted from QBAMs')
    parser.add_argument('--chkpt_path',     default='',                 help='where the model checkpoint is')
    parser.add_argument('--img_path',       default='',                 help='where the model saves loss graphs')
    parser.add_argument('--results_path',   default='',                 help='where the model saves text files with test predictions')
    parser.add_argument('--batch_size',     type=int,   default=20,     help='Model\'s batch size.')

    if args is None: 
        return parser.parse_args()      ## For calling through command line
    return parser.parse_args(args)      ## For calling through notebook.


def train(model, train_loader, optimizer, criterion):
    model.train()
    for data in train_loader:
        data = data.to(model.device)  # Move data to the same device as the model
        out = model(data)
        loss = criterion(out, data.y.reshape(-1, model.output_dim))
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
            loss = criterion(out, data.y.reshape(-1, model.output_dim))
            total_loss += loss.item()

            if print_met:
                print(f"Predicted: {out}, True: {data.y.reshape(-1, model.output_dim)}, CCE: {loss.item()}")

    avg_loss = total_loss / len(loader.dataset)
    return math.sqrt(avg_loss)

def train_model(train_loader, val_loader, test_loader, model, output_filepath, img_path, learning_rate, num_epochs, convergence_epsilon = 0.05):

    best_cce = 99999999999
    prev_cce = None

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print("Using", device)
    model = model.to(device)
    model.device = device
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = CrossEntropyLoss()

    train_losses = []
    val_losses = []
    test_losses = []

    for epoch in tqdm(range(1, num_epochs + 1), desc="Training Epochs"):
        train(model, train_loader, optimizer, criterion)
        train_cce = test(model, train_loader, criterion, False)
        val_cce = test(model, val_loader, criterion, False)
        test_cce = test(model, test_loader, criterion, False)

        train_losses.append(train_cce)
        val_losses.append(val_cce)
        test_losses.append(test_cce)

        # if prev_cce and abs(train_cce - prev_cce) < convergence_epsilon: break

        # prev_cce = train_cce

        if epoch % 20 == 0:
            print(f'\nEpoch: {epoch:03d}, Train CCE: {train_cce:.4f}, Val CCE: {val_cce:.4f}\n')

    train_losses = np.array(train_losses)
    val_losses = np.array(val_losses)
    test_losses = np.array(test_losses)

    torch.save(model.state_dict(), output_filepath)
    print("Saved the model to:", output_filepath)

    plt.figure(figsize=(10, 6))
    plt.plot(train_losses, label='Training CCE')
    plt.plot(val_losses, label='Validation CCE')
    plt.plot(test_losses, label='Test CCE')
    plt.xlabel('Epoch')
    plt.ylabel('CCE')
    plt.title('Training and Validation CCE')
    plt.legend()
    plt.savefig(img_path)
    plt.close()
    print(f"Saved graph to {img_path}")

    return train_losses[-1], val_losses[-1], test_losses[-1]


def final_test(model, loader, write_to_file, print_met=True):
    correct_preds = 0
    f = open(write_to_file, "w") if write_to_file else None

    with torch.no_grad():
        for data in loader:
            data = data.to(model.device)
            out = model(data)

            correct_preds += torch.sum(torch.argmax(out.item(),dim=-1)==torch.argmax(data.y.reshape(-1, model.output_dim), dim=-1)).item()

            if print_met:
                print(f"Predicted: {out}, True: {data.y.reshape(-1, model.output_dim)}, Accuracy: {correct_preds/len(out)}")
            if f:
                f.write(f"Predicted: {out}, True: {data.y.reshape(-1, model.output_dim)}, Accuracy: {correct_preds/len(out)}\n")

    avg_acc = correct_preds / len(loader.dataset)
    if f: 
        f.write(f"Average Accuracy: {avg_acc}\n")
        print(f"Wrote Prediciton Outputs to {write_to_file}")
        f.close()
    return avg_acc

def test_model(test_loader, model, task, write_to_file=None):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    model.device = device

    model.eval()
    test_acc = final_test(model, test_loader, write_to_file=write_to_file, print_met=False)

    print(f'Test Accuracy: {test_acc:.4f}')
    print()
    return test_acc
    


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
    for data_type in ['Donor']:
        data_dirs[f"Train_{data_type}"] = f"{args.data}/{data_type}/Train_{data_type}.pkl"
        data_dirs[f"Valid_{data_type}"] = f"{args.data}/{data_type}/Valid_{data_type}.pkl"
        data_dirs[f"Test_{data_type}"] = f"{args.data}/{data_type}/Test_{data_type}.pkl"

    model_constructors = {
        "G2_D2": GCNs.GCN_G2_D2,
        "G2_D3": GCNs.GCN_G2_D3,
        "G2_D4": GCNs.GCN_G2_D4,
        "G2_D5": GCNs.GCN_G2_D5,
        "G3_D2": GCNs.GCN_G3_D2,
        "G3_D3": GCNs.GCN_G3_D3,
        "G3_D4": GCNs.GCN_G3_D4,
        "G3_D5": GCNs.GCN_G3_D5,
        "G4_D2": GCNs.GCN_G4_D2,
        "G4_D3": GCNs.GCN_G4_D3,
        "G4_D4": GCNs.GCN_G4_D4,
        "G4_D5": GCNs.GCN_G4_D5,
        "G5_D2": GCNs.GCN_G5_D2,
        "G5_D3": GCNs.GCN_G5_D3,
        "G5_D4": GCNs.GCN_G5_D4,
        "G5_D5": GCNs.GCN_G5_D5
    }


    target = args.pred 
    train_pickle_file = data_dirs[f"Train_{target}"]
    val_pickle_file = data_dirs[f"Valid_{target}"]
    test_pickle_file = data_dirs[f"Test_{target}"]

    train_dataset = load_dataset_from_pickle(train_pickle_file)
    val_dataset = load_dataset_from_pickle(val_pickle_file)
    test_dataset = load_dataset_from_pickle(test_pickle_file)

    check_for_nan(train_dataset)
    check_for_nan(val_dataset)
    check_for_nan(test_dataset)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset)


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

    lr_epoch = [(0.0005, 150), (0.00075, 150), (0.001, 50), (0.0025, 50), (0.005, 50)]

    train_data = {"Learning Rate": [lr for lr, _ in lr_epoch]}
    val_data = {"Learning Rate": [lr for lr, _ in lr_epoch]}
    test_data = {"Learning Rate": [lr for lr, _ in lr_epoch]}
    test_acc_data = {"Learning Rate": [lr for lr, _ in lr_epoch]}

    #Tuning Modular
    for num_gcn in ([2, 3, 4, 5]):
        for num_dense in ([2, 3, 4, 5]):
            arch_string = f"G{num_gcn}_D{num_dense}"
            train_losses, val_losses, test_losses, test_accuracies = [], [], [], []
            for (learning_rate, num_epochs) in lr_epoch:
                print("___________________________________")
                print()
                print("Learning Rate:", learning_rate)
                print("Epochs:", num_epochs )
                print(f"Num GCN Layers {num_gcn}")
                print(f"Num Dense Layers {num_dense}")
                print("___________________________________")

                hyper_param_dir = f"{args.pred}/lr{learning_rate}_e{num_epochs}" 
                Path(f'{args.chkpt_path}/{hyper_param_dir}').mkdir(parents=True, exist_ok=True)
                output_filepath = f'{args.chkpt_path}/{hyper_param_dir}/g{num_gcn}_d{num_dense}_Abs_model.pth'
                Path(f'{args.img_path}/{hyper_param_dir}').mkdir(parents=True, exist_ok=True)
                img_path = f"{args.img_path}/{hyper_param_dir}/g{num_gcn}_d{num_dense}_CCE_Loss_Graph.jpg"

                model_class = model_constructors[arch_string]
                model = model_class(num_features, num_targets)

                train_loss, val_loss, test_loss = train_model(train_loader, val_loader, test_loader, model, output_filepath, img_path, learning_rate, num_epochs)

                Path(f'{args.results_path}/{hyper_param_dir}').mkdir(parents=True, exist_ok=True)
                results_file = f'{args.results_path}/{hyper_param_dir}/g{num_gcn}_d{num_dense}_sample_preds.txt'
                test_acc = test_model(test_loader, model, task=args.pred, write_to_file=results_file)

                for l, stat in zip([train_losses, val_losses, test_losses, test_accuracies], [train_loss, val_loss, test_loss, test_acc]):
                    l.append(stat)

            for d, l in zip([train_data, val_data, test_data, test_acc_data], [train_losses, val_losses, test_losses, test_accuracies]):
                d[arch_string] = l

    #Create performance summaries
    df_filepath = f"{args.results_path}/{args.pred}_stats.xlsx"
    with pd.ExcelWriter(df_filepath) as writer:
        for data, split in zip([train_data, val_data, test_data, test_acc_data], ["Train Loss", "Val Loss", "Test Loss", "Test Acc"]):
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name=split)

    print(f"Wrote performance summary to {df_filepath}")

## END UTILITY METHODS
##############################################################################

if __name__ == '__main__':
    main(parse_args())