import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torchvision.transforms as T
import multiprocessing
from time import time
from torch.utils.data import DataLoader
from matplotlib import pyplot as plt

from dataset import *

class DDH3(nn.Module):
    '''
    # ==========================================================================
    # Discriminative Deep Hashing for Scalable Face Image Retrieval
    # https://www.ijcai.org/proceedings/2017/0315.pdf
    # ==========================================================================

    Image resized to 32x32, batch size of 256

    Conv1 = 3x3 kernel, 1 stride, 20 dim (output 31x31)
    Batch
    Pool1 = 2x2 kernel (output 15x15)

    Conv2 = 2x2 kernel, 1 stride, 40 dim (output 14x14)
    Batch
    Pool2 = 2x2 kernel (output 7x7)

    Conv3 = 2x2 kernel, 1 stride, 60 dim (output 6x6)
    Batch
    Pool3 = 2x2 kernel (output 3x3)

    Conv4 = 2x2 kernel, 1 stride, 80 dim (output 2x2)
    Batch

    Merge = 60*3*3 + 80*2*2 = 860

    Split into K groups, let K = 96

    480 face features
    48 groups of 10 features
    48-bits

    # ==========================================================================
    # Simultaneous Feature Learning and Hash Coding with Deep Neural Networks
    # https://arxiv.org/pdf/1504.03410.pdf
    # ==========================================================================
    '''
    def __init__(self, hash_dim=48, split_num=10):
        super().__init__()
        self.cn1 = nn.Conv2d(3, 20, kernel_size=3)
        nn.init.kaiming_normal_(self.cn1.weight)
        self.bn1 = nn.BatchNorm2d(20)
        self.mp1 = nn.MaxPool2d(2)

        self.cn2 = nn.Conv2d(20, 40, kernel_size=2)
        nn.init.kaiming_normal_(self.cn2.weight)
        self.bn2 = nn.BatchNorm2d(40)
        self.mp2 = nn.MaxPool2d(2)

        self.cn3 = nn.Conv2d(40, 60, kernel_size=2)
        nn.init.kaiming_normal_(self.cn3.weight)
        self.bn3 = nn.BatchNorm2d(60)
        self.mp3 = nn.MaxPool2d(2)

        self.cn4 = nn.Conv2d(60, 80, kernel_size=2)
        nn.init.kaiming_normal_(self.cn4.weight)
        self.bn4 = nn.BatchNorm2d(80)

        # merge layer
        self.mg1 = Merge()
        self.fc1 = nn.Linear(29180, hash_dim*split_num)
        nn.init.kaiming_normal_(self.fc1.weight)
        self.bn5 = nn.BatchNorm2d(hash_dim*split_num)

        # hash layer
        self.fc2 = nn.Linear(hash_dim*split_num, hash_dim)

    def forward(self, X):
        l1 = self.mp1(F.relu(self.bn1(self.cn1(X))))
        l2 = self.mp2(F.relu(self.bn2(self.cn2(l1))))
        l3 = self.mp3(F.relu(self.bn3(self.cn3(l2))))
        l4 = F.relu(self.bn4(self.cn4(l3)))
        # merge of output from layer 3 and 4
        l5 = self.mg1(l3, l4)
        # face feature layer
        l6 = F.relu(self.fc1(l5))
        # divide and encode
        codes = self.fc2(l6)
        return torch.tanh(codes), None

class Merge(nn.Module):
    '''
    Implementation of the Merged Layer in,

    Discriminative Deep Hashing for Scalable Face Image Retrieval
    https://www.ijcai.org/proceedings/2017/0315.pdf
    '''
    def __init__(self):
        super(Merge, self).__init__()

    def forward(self, X1, X2):
        X1, X2 = self._flatten(X1), self._flatten(X2)
        return self._merge(X1, X2)

    def _flatten(self, X):
        N = X.shape[0]
        return X.view(N, -1)

    def _merge(self, X1, X2):
        return torch.cat((X1, X2), 1)

# ==========================
# Hyperparameters
# ==========================

# number of epochs to train
NUM_EPOCHS = 40
# the number of hash bits in the output
HASH_DIM = 48
# the distance to use for calculating precision/recall
HAMM_RADIUS = 2
# top_k closet images to score for mean average precision
TOP_K = 50
# optimizer parameters
OPTIM_PARAMS = {
    "lr": 1e-2,
    "weight_decay": 2e-4
}
CUSTOM_PARAMS = {
    "dist_threshold": 6, # distance threshold
    "alpha": 1e-10, # quantization error
    "print_iter": 1, # print every n iterations
    "eps": 1e-8, # term added to l2_distance
    "gamma": 1e-3, # negative slope when calculating threshold
    "img_size": 128
}
BATCH_SIZE = {
    # "train": 512,
    "train": 32,
    "gallery": 128,
    "val": 512,
    "test": 512
}
LOADER_PARAMS = {
    "num_workers": multiprocessing.cpu_count() - 2,
    # "num_workers": 1
}

# ==========================
# Setup
# ==========================

# uncomment to reset the data
# undo_create_set("val")
# undo_create_set("test")
# create_set("val")
# create_set("test")

TRANSFORMS = [
    T.Resize((CUSTOM_PARAMS['img_size'], CUSTOM_PARAMS['img_size'])),
    T.ToTensor()
]

data_train = FaceScrubDataset(type="label",
                              mode="train",
                              transform=TRANSFORMS,
                              hash_dim=HASH_DIM)

data_val = FaceScrubDataset(type="label",
                            mode="val",
                            transform=TRANSFORMS,
                            hash_dim=HASH_DIM)

data_test = FaceScrubDataset(type="label",
                             mode="test",
                             transform=TRANSFORMS,
                             hash_dim=HASH_DIM)

# for training use, shuffling
loader_train = DataLoader(data_train,
                          batch_size=BATCH_SIZE["train"],
                          shuffle=True,
                          **LOADER_PARAMS)

# for use as gallery, no shuffling
loader_gallery = DataLoader(data_train,
                          batch_size=BATCH_SIZE["gallery"],
                          shuffle=False,
                          **LOADER_PARAMS)

loader_val = DataLoader(data_val,
                          batch_size=BATCH_SIZE["val"],
                          shuffle=False,
                          **LOADER_PARAMS)
loader_test = DataLoader(data_test,
                          batch_size=BATCH_SIZE["test"],
                          shuffle=False,
                          **LOADER_PARAMS)

model_class = DDH3
model = model_class(hash_dim=HASH_DIM)
optimizer = optim.Adam(model.parameters(), **OPTIM_PARAMS)

def train(model, loader, optim, logger, **kwargs):
    '''
    Train for one epoch.
    '''
    device = kwargs.get("device", torch.device("cpu"))
    print_iter = kwargs.get("print_iter", 40)
    # the distance threshold above which the dissimilar pairs will contribute 0
    # to loss.
    mu = kwargs.get("dist_threshold", 2)
    # quantization loss regularizer
    alpha = kwargs.get("alpha", 0.01)

    model.to(device=device)
    # set model to train mode
    model.train()

    for num_iter, (X, y) in enumerate(loader):
        optim.zero_grad()

        half_size = BATCH_SIZE["train"] // 2
        half_size = len(X) // 2 if len(X) < half_size else half_size
        X1 = X[:half_size].float().to(device=device)
        X2 = X[half_size:].float().to(device=device)
        y1 = y[:half_size].long().to(device=device)
        y2 = y[half_size:].long().to(device=device)
        with torch.no_grad():
            if len(X2) > len(X1):
                # get rid of the last row
                X2 = X2[:-1]
                y2 = y2[:-1]

        # figure out the ground truth table
        y1_gt = y1[None, :].repeat(half_size, 1)
        y2_gt = y2[:, None].repeat(1, half_size)
        # 1 for similar pairs, 0 for dissimilar pairs
        sim_gt = (y1_gt == y2_gt).float()
        dissim_gt = (1 - sim_gt)

        C1, _ = model(X1)
        C2, _ = model(X2)

        l2_dist = ((C1[:, None, :] - C2) ** 2 + 1e-8).sum(dim=2).sqrt()
        # minimize l2_dist for similar pairs (gt at i, j == 1)
        similar_loss = (sim_gt * l2_dist).sum()
        similar_loss /= (sim_gt + 1).sum()
        # maximize l2_dist for dissimilar pairs
        threshold = F.leaky_relu(mu - l2_dist,
                                 negative_slope=CUSTOM_PARAMS['gamma'])
        dissimilar_loss = ((1 - sim_gt) * threshold).sum()
        dissimilar_loss /= (dissim_gt.sum() + 1)
        # similarity loss
        sim_loss = similar_loss + dissimilar_loss
        # quantization loss
        quant_loss = alpha * \
                        ((C1.abs() - 1).abs() + ((C2.abs() - 1)).abs()).sum()
        set_trace()
        # total_loss
        loss = sim_loss + quant_loss
        # back-propagate
        loss.backward()
        # apply gradient
        optim.step()

        if (num_iter+1) % print_iter == 0:
            logger.write(
                "iter {}/{} ".format(num_iter+1, len(loader)) +
                "- quant loss: {:.4f}, sim loss: {:.4f}, dissim loss: {:.4f}"
                    .format(quant_loss.item(), similar_loss.item(),
                            dissimilar_loss.item()))
