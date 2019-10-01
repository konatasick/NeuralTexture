import argparse
import os
import tensorboardX
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam
from torch.utils.data import DataLoader

import config
from dataset.uv_dataset import UVDataset, collect_fn
from model.renderer import Renderer

parser = argparse.ArgumentParser()
parser.add_argument('--pyramidw', type=int, default=config.PYRAMID_W)
parser.add_argument('--pyramidh', type=int, default=config.PYRAMID_H)

parser.add_argument('--data', type=str, default=config.DATA_DIR, help='directory to data')
parser.add_argument('--checkpoint', type=str, default=config.CHECKPOINT_DIR, help='directory to save checkpoint')
parser.add_argument('--logdir', type=str, default=config.LOG_DIR, help='directory to save checkpoint')
parser.add_argument('--train', default=config.TRAIN_SET)
parser.add_argument('--epoch', type=int, default=config.EPOCH)
parser.add_argument('--cropw', type=int, default=config.CROP_W)
parser.add_argument('--croph', type=int, default=config.CROP_H)
parser.add_argument('--batch', type=int, default=config.BATCH_SIZE)
parser.add_argument('--lr', default=config.LEARNING_RATE)
parser.add_argument('--betas', default=config.BETAS)
parser.add_argument('--l2', default=config.L2_WEIGHT_DECAY)
parser.add_argument('--eps', default=config.EPS)
args = parser.parse_args()


if __name__ == '__main__':

    named_tuple = time.localtime()
    time_string = time.strftime("%m_%d_%Y_%H_%M", named_tuple)
    writer = tensorboardX.SummaryWriter(logdir=os.path.join(args.logdir, time_string))

    dataset = UVDataset(args.data, args.train, args.cropw, args.croph)
    dataloader = DataLoader(dataset, batch_size=args.batch, shuffle=True, num_workers=4)

    model = Renderer(args.pyramidw, args.pyramidh)
    model = nn.DataParallel(model.cuda())
    model.train()
    torch.set_grad_enabled(True)

    optimizer = Adam([
        {'params': model.texture.layer1.parameters(), 'weight_decay': args.l2[0]},
        {'params': model.texture.layer2.parameters(), 'weight_decay': args.l2[1]},
        {'params': model.texture.layer3.parameters(), 'weight_decay': args.l2[2]},
        {'params': model.texture.layer4.parameters(), 'weight_decay': args.l2[3]}],
        lr=args.lr, betas=args.betas, eps=args.eps)
    criterion = nn.L1Loss()
    step = 0

    print('Training started')
    for i in range(args.epoch):
        print('Epoch {}'.format(i+1))
        for samples in dataloader:
            images, uv_maps, masks = samples
            step += images.shape[0]
            preds = model(uv_maps.cuda()).cpu()
            preds = torch.masked_select(preds, masks)
            images = torch.masked_select(images, masks)
            loss = criterion(preds, images)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            writer.add_scalar('train/loss', loss.item(), step)
            print('loss at step {}: {}'.format(step, loss.item()))

        # save checkpoint
        print('Saving checkpoint')
        torch.save(model.state_dict(), args.checkpoint+time_string+'/epoch_{}.pt'.format(i+1))

