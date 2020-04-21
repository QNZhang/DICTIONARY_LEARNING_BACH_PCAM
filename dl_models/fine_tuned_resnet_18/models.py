# -*- coding: utf-8 -*-
""" dl_models/fine_tuned_resnet_18/model """

from __future__ import print_function, division

import copy
import os
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
import numpy as np
import torchvision
from torchvision import models, transforms
import matplotlib.pyplot as plt

from constants.constants import Label
from dl_models.fine_tuned_resnet_18 import constants as local_constants
import settings
from utils.datasets.bach import BACHDataset


class TransferLearningResnet18:
    """"
    Manages the resnet18 by applying transfer learning and optionally fine tuning

    Inspired on: https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html

    Usage:
        model = TransferLearningResnet18(fine_tune=True)
        model.training_data_plot_grid()
        model.train(num_epochs=25)
        model.save('mymodel.pt')
        model.visualize_model()
        model.test()

        model2 = TransferLearningResnet18(fine_tune=True)
        model2.load('weights/resnet18_fine_tuned.pt')
        model.visualize_model()
        model2.test()
    """
    # TODO: Create unit tests with a very small dataset
    TRAIN = 'train'
    # VALIDATION = 'validation'
    # NOTE: test during training refers to the validtion dataset; but during
    #       testing it refers to the test dataset
    # TODO: modify the code to consider test and validation separately and properly
    TEST = 'test'

    def __init__(self, *args, **kwargs):
        """
        Initializes the instance attributes

        Args:
            data_transforms (dict): for its structure see get_default_data_transforms method
            device  (torch.device): device were model will executed
            fine_tune       (bool): whether perform fine-tuning or use the ConvNet as a fixed feature extractor
        """
        self.data_transforms = kwargs.get('data_transforms', self.get_default_data_transforms())
        assert isinstance(self.data_transforms, dict)
        self.device = kwargs.get('device', torch.device("cuda:0" if torch.cuda.is_available() else "cpu"))
        assert isinstance(self.device, torch.device)
        self.fine_tune = kwargs.get('fine_tune', False)
        assert isinstance(self.fine_tune, bool)
        self.image_datasets = {
            x: BACHDataset(
                os.path.join(settings.OUTPUT_FOLDER, x), transform=self.data_transforms[x])
            for x in [self.TRAIN, self.TEST]
        }
        self.dataloaders = {
            x: torch.utils.data.DataLoader(
                self.image_datasets[x], batch_size=settings.BATCH_SIZE,
                shuffle=True, num_workers=settings.NUM_WORKERS)
            for x in [self.TRAIN, self.TEST]
        }
        self.dataset_sizes = {x: len(self.image_datasets[x]) for x in [self.TRAIN, self.TEST]}

        self.init_model()

    @staticmethod
    def get_default_data_transforms():
        """
        Returns the default data transformations to be appliend to the train and test datasets
        """
        # TODO: Try with the commented transforms
        return {
            'train': transforms.Compose([
                # transforms.RandomResizedCrop(224),
                # transforms.RandomHorizontalFlip(),
                transforms.ToTensor(),
                transforms.Normalize(local_constants.MEAN, local_constants.STD)
            ]),
            'test': transforms.Compose([
                # transforms.Resize(256),
                # transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(local_constants.MEAN, local_constants.STD)
            ]),
        }

    def init_model(self):
        """ Initializes the model for fine tuning or as a fixed feature extractor """
        self.model = models.resnet18(pretrained=True)

        # If want to use the ConvNet as fixed feature extractor (no fine tuning)
        if not self.fine_tune:
            for param in self.model.parameters():
                param.requires_grad = False

        self.num_ftrs = self.model.fc.in_features

        # Changing last layer
        self.model.fc = nn.Linear(self.num_ftrs, len(Label.CHOICES))

        self.model = self.model.to(self.device)
        self.criterion = nn.CrossEntropyLoss()

        if self.fine_tune:
            # Observe that all parameters are being optimized
            self.optimizer = optim.SGD(self.model.parameters(), lr=0.001, momentum=0.9)
        else:
            # Observe that only parameters of final layer are being optimized as
            # opposed to before.
            self.optimizer = optim.SGD(self.model.fc.parameters(), lr=0.001, momentum=0.9)

        # Decay LR by a factor of 0.1 every 7 epochs
        self.scheduler = lr_scheduler.StepLR(self.optimizer, step_size=7, gamma=0.1)

    @staticmethod
    def imshow(inp, title=None):
        """
        Imshow for Tensor

        Args:
            inp            (torch.Tensor): Tensor image
            title (list or tuple or None): Image title
        """
        assert isinstance(inp, torch.Tensor)
        assert isinstance(title, (list, tuple)) or title is None

        inp = inp.numpy().transpose((1, 2, 0))
        mean = np.array(local_constants.MEAN)
        std = np.array(local_constants.STD)
        inp = std * inp + mean
        inp = np.clip(inp, 0, 1)
        plt.imshow(inp)
        if title is not None:
            plt.title(title)
        plt.pause(0.001)  # pause a bit so that plots are updated

    def training_data_plot_grid(self):
        """ Gets a batch of training data and plots a grid  """
        inputs, classes = next(iter(self.dataloaders[self.TRAIN])).values()

        # Make a grid from batch
        out = torchvision.utils.make_grid(inputs)

        self.imshow(out, title=[Label.get_name(x.item()) for x in classes])

    def load(self, state_dict_path):
        """ Reads and loads the model state dictionary provided """
        assert os.path.isfile(state_dict_path)

        self.model.load_state_dict(torch.load(state_dict_path))

    def save(self, filename):
        """
        Saves the model in a file <filename>.pt at settings.MODEL_SAVE_FOLDER

        Args:
            filename (str): filename with '.pt' extension
        """
        assert isinstance(filename, str)
        assert filename.endswith('.pt')

        torch.save(self.model.state_dict(), os.path.join(settings.MODEL_SAVE_FOLDER, filename))

    def train(self, num_epochs=25):
        """
        * Trains and evaluates the model
        * Sets the best model to self.model

        Args:
            num_epochs (int): number of epochs
        """
        assert isinstance(num_epochs, int)
        assert num_epochs > 0

        since = time.time()
        best_model_wts = copy.deepcopy(self.model.state_dict())
        best_acc = 0.0

        for epoch in range(num_epochs):
            print('Epoch {}/{}'.format(epoch, num_epochs - 1))
            print('-' * 10)

            # Each epoch has a training and validation phase
            for phase in [self.TRAIN, self.TEST]:
                if phase == self.TRAIN:
                    self.model.train()  # Set model to training mode
                else:
                    self.model.eval()   # Set model to evaluate mode

                running_loss = 0.0
                running_corrects = 0

                # Iterate over data.
                for data in self.dataloaders[phase]:
                    inputs = data['image'].to(self.device)
                    labels = data['target'].to(self.device)

                    # zero the parameter gradients
                    self.optimizer.zero_grad()

                    # forward
                    # track history if only in train
                    with torch.set_grad_enabled(phase == self.TRAIN):
                        outputs = self.model(inputs)
                        _, preds = torch.max(outputs, 1)
                        loss = self.criterion(outputs, labels)

                        # backward + optimize only if in training phase
                        if phase == self.TRAIN:
                            loss.backward()
                            self.optimizer.step()

                    # statistics
                    running_loss += loss.item() * inputs.size(0)
                    running_corrects += torch.sum(preds == labels.data)

                if phase == self.TRAIN:
                    self.scheduler.step()

                epoch_loss = running_loss / self.dataset_sizes[phase]
                epoch_acc = running_corrects.double() / self.dataset_sizes[phase]

                print('{} Loss: {:.4f} Acc: {:.4f}'.format(phase, epoch_loss, epoch_acc))

                # deep copy the model
                if phase == self.TEST and epoch_acc > best_acc:
                    best_acc = epoch_acc
                    best_model_wts = copy.deepcopy(self.model.state_dict())

            print()

        time_elapsed = time.time() - since
        print('Training complete in {:.0f}m {:.0f}s'.format(time_elapsed // 60, time_elapsed % 60))
        print('Best test Acc: {:4f}'.format(best_acc))

        # load best model weights
        self.model.load_state_dict(best_model_wts)

    def test(self):
        """
        Test the model and prints the results
        """
        since = time.time()
        self.model.eval()
        corrects = 0

        for data in self.dataloaders[self.TEST]:
            inputs = data['image'].to(self.device)
            labels = data['target'].to(self.device)

            with torch.no_grad():
                outputs = self.model(inputs)
                _, preds = torch.max(outputs, 1)

            corrects += torch.sum(preds == labels.data)

        accuracy = corrects.double() / self.dataset_sizes[self.TEST]
        print('Acc: {:.4f}'.format(accuracy))

        time_elapsed = time.time() - since
        print('Testing complete in {:.0f}m {:.0f}s'.format(
            time_elapsed // 60, time_elapsed % 60))

    def visualize_model(self, num_images=6):
        """
        Plots some images with its predicitons

        Args:
            num_images (int) : number of images to plot
        """
        assert isinstance(num_images, int)
        assert num_images > 0

        was_training = self.model.training
        self.model.eval()
        images_so_far = 0
        fig = plt.figure()

        with torch.no_grad():
            for i, data in enumerate(self.dataloaders[self.TEST]):
                inputs = data['image'].to(self.device)
                labels = data['target'].to(self.device)

                outputs = self.model(inputs)
                _, preds = torch.max(outputs, 1)

                for j in range(inputs.size()[0]):
                    images_so_far += 1
                    ax = plt.subplot(num_images//2, 2, images_so_far)
                    ax.axis('off')
                    ax.set_title('predicted: {}'.format(Label.get_name(preds[j].item())))
                    self.imshow(inputs.cpu().data[j])

                    if images_so_far == num_images:
                        self.model.train(mode=was_training)
                        return

            self.model.train(mode=was_training)
