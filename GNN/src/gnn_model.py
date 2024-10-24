import torch
import torch.nn.functional as F
from torch_geometric.nn import GATv2Conv, global_mean_pool, BatchNorm, JumpingKnowledge
from torch.nn import Linear, Dropout

class GCN(torch.nn.Module):
    def __init__(self, num_node_features, output_dim, hidden_channels=128, num_heads=8):
        super().__init__()
        self.num_node_features = num_node_features
        self.output_dim = output_dim
        self.hidden_channels = hidden_channels
        self.num_heads = num_heads

        self.conv1 = GATv2Conv(self.num_node_features, self.hidden_channels, heads=self.num_heads, concat=True, edge_dim=1)
        self.norm1 = BatchNorm(self.hidden_channels * self.num_heads)

        self.conv2 = GATv2Conv(self.hidden_channels * self.num_heads, self.hidden_channels, heads=self.num_heads, concat=True, edge_dim=1)
        self.norm2 = BatchNorm(self.hidden_channels * self.num_heads)
        
        self.conv3 = GATv2Conv(self.hidden_channels * self.num_heads, self.output_dim, heads=1, concat=False, edge_dim=1)
        self.norm3 = BatchNorm(self.output_dim)
        
        self.dropout = Dropout(p=0.5)

        self.linear1 = Linear(self.output_dim, self.hidden_channels)
        self.linear2 = Linear(self.hidden_channels, self.output_dim)

    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch

        x = self.conv1(x, edge_index)
        x = self.norm1(x)
        x = F.leaky_relu(x)

        x = self.conv2(x, edge_index)
        x = self.norm2(x)
        x = F.leaky_relu(x)

        x = self.conv3(x, edge_index)
        x = self.norm3(x)
        x = F.leaky_relu(x)

        x = global_mean_pool(x, batch)

        x = F.leaky_relu(self.linear1(x))
        x = self.dropout(x)
        x = self.linear2(x)

        return x

# import torch
# import torch.nn.functional as F
# from torch_geometric.nn import GATv2Conv, global_mean_pool, BatchNorm
# from torch.nn import Linear, Dropout

# class GCN(torch.nn.Module):
#     def __init__(self, num_node_features, output_dim, hidden_channels=128, num_heads=8):
#         super().__init__()
#         self.num_node_features = num_node_features
#         self.output_dim = output_dim
#         self.hidden_channels = hidden_channels
#         self.num_heads = num_heads

#         self.conv1 = GATv2Conv(self.num_node_features, self.hidden_channels, heads=self.num_heads, concat=True, edge_dim=0)
#         self.norm1 = BatchNorm(self.hidden_channels * self.num_heads)

#         self.conv2 = GATv2Conv(self.hidden_channels * self.num_heads, self.hidden_channels, heads=self.num_heads, concat=True, edge_dim=0)
#         self.norm2 = BatchNorm(self.hidden_channels * self.num_heads)
        
#         self.conv3 = GATv2Conv(self.hidden_channels * self.num_heads, self.output_dim, heads=1, concat=False, edge_dim=0)
#         self.norm3 = BatchNorm(self.output_dim)
        
#         self.dropout = Dropout(p=0.5)

#         self.linear1 = Linear(self.output_dim, self.hidden_channels)
#         self.linear2 = Linear(self.hidden_channels, self.output_dim)

#     def forward(self, data):
#         x, edge_index, batch = data.x, data.edge_index, data.batch

#         # print(x)
#         # print("--------------------")

#         x = self.conv1(x, edge_index)
#         x = self.norm1(x)
#         x = F.leaky_relu(x)

#         x = self.conv2(x, edge_index)
#         x = self.norm2(x)
#         x = F.leaky_relu(x)

#         x = self.conv3(x, edge_index)
#         x = self.norm3(x)
#         x = F.leaky_relu(x)

#         x = global_mean_pool(x, batch)

#         x = F.leaky_relu(self.linear1(x))

#         x = self.dropout(x)
#         x = self.linear2(x)

#         return x.view(-1)