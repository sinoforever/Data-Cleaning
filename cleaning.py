from __future__ import absolute_import
from __future__ import print_function
from future.standard_library import install_aliases
import os
import gzip
import struct
import array
import autograd.numpy as np
import autograd.numpy.random as npr
import autograd.scipy.stats.norm as norm
from tree import NoisyLabeler
from autograd.optimizers import adam
from autograd.scipy.misc import logsumexp
from autograd import grad
from urllib.request import urlretrieve
import matplotlib.pyplot as plt
import matplotlib.image
install_aliases()


class data_reader():

    def download(self, url, filename):
        if not os.path.exists('data'):
            os.makedirs('data')
        out_file = os.path.join('data', filename)
        if not os.path.isfile(out_file):
            urlretrieve(url, out_file)

    def mnist(self):
        base_url = 'http://yann.lecun.com/exdb/mnist/'

        def parse_labels(filename):
            with gzip.open(filename, 'rb') as fh:
                magic, num_data = struct.unpack(">II", fh.read(8))
                return np.array(array.array("B", fh.read()), dtype=np.uint8)

        def parse_images(filename):
            with gzip.open(filename, 'rb') as fh:
                magic, num_data, rows, cols = struct.unpack(">IIII", fh.read(16))
                return np.array(array.array("B", fh.read()), dtype=np.uint8).reshape(num_data, rows, cols)

        for filename in ['train-images-idx3-ubyte.gz',
                         'train-labels-idx1-ubyte.gz',
                         't10k-images-idx3-ubyte.gz',
                         't10k-labels-idx1-ubyte.gz']:
            self.download(base_url + filename, filename)

        train_images = parse_images('data/train-images-idx3-ubyte.gz')
        train_labels = parse_labels('data/train-labels-idx1-ubyte.gz')
        test_images = parse_images('data/t10k-images-idx3-ubyte.gz')
        test_labels = parse_labels('data/t10k-labels-idx1-ubyte.gz')

        return train_images, train_labels, test_images, test_labels

    def load_mnist(self):
        print('=== Loading MNIST Data ===')

        partial_flatten = lambda x: np.reshape(x, (x.shape[0], np.prod(x.shape[1:])))
        one_hot = lambda x, k: np.array(x[:, None] == np.arange(k)[None, :], dtype=int)
        train_images, train_labels, test_images, test_labels = self.mnist()
        train_images = partial_flatten(train_images) / 255.0
        test_images = partial_flatten(test_images) / 255.0
        train_labels = one_hot(train_labels, 10)
        test_labels = one_hot(test_labels, 10)
        N_data = train_images.shape[0]

        return N_data, train_images, train_labels, test_images, test_labels


class image_saver():

    def plot_images(self, images, ax, ims_per_row=5, padding=5,
                    digit_dimensions=(28, 28), cmap=matplotlib.cm.binary,
                    vmin=None, vmax=None):
        """Images should be a (N_images x pixels) matrix."""
        N_images = images.shape[0]
        N_rows = np.int32(np.ceil(float(N_images) / ims_per_row))
        pad_value = np.min(images.ravel())
        concat_images = np.full(((digit_dimensions[0] + padding) * N_rows + padding,
                                 (digit_dimensions[1] + padding) * ims_per_row + padding), pad_value)
        for i in range(N_images):
            cur_image = np.reshape(images[i, :], digit_dimensions)
            row_ix = i // ims_per_row
            col_ix = i % ims_per_row
            row_start = padding + (padding + digit_dimensions[0]) * row_ix
            col_start = padding + (padding + digit_dimensions[1]) * col_ix
            concat_images[row_start: row_start + digit_dimensions[0],
                          col_start: col_start + digit_dimensions[1]] = cur_image
        cax = ax.matshow(concat_images, cmap=cmap, vmin=vmin, vmax=vmax)
        plt.xticks(np.array([]))
        plt.yticks(np.array([]))
        return cax

    def save_images(self, images, filename, **kwargs):
        fig = plt.figure(1)
        fig.clf()
        ax = fig.add_subplot(111)
        self.plot_images(images, ax, **kwargs)
        fig.patch.set_visible(False)
        ax.patch.set_visible(False)
        plt.savefig(filename)


def logit_ll(x, y, w):
    return np.sum(np.multiply(y, (np.dot(x, w.T) - np.tile(logsumexp(np.dot(x, w.T), axis=1), 10).reshape(10, x.shape[0]).T)))


def logit_ll_map(x, y, w, sigma):
    return np.sum(np.multiply(y, (np.dot(x, w.T) - np.tile(logsumexp(np.dot(x, w.T), axis=1), 10).reshape(10, x.shape[0]).T))) - np.sum(0.5 * np.log(2 * sigma**2 * np.pi) + np.power(w, 2)/2/sigma**2)


def fit_logistic(images, labels):
    x = images
    y = labels
    w = np.zeros((labels.shape[1], images.shape[1]))
    gradient = grad(logit_ll, argnum=2)
    for i in range(5000):
        w += gradient(x, y, w) * 0.001
    return w


def fit_logistic_map(images, labels, sigma):
    x = images
    y = labels
    w = np.zeros((labels.shape[1], images.shape[1]))
    gradient = grad(logit_ll_map, argnum=2)
    for i in range(5000):
        w += gradient(x, y, w, sigma) * 0.001
    return w


def pred_ll(x, w):
    return logll(np.dot(x, w.T))


def logll(K):
    return K - np.tile(logsumexp(K, axis=1), 10).reshape(10, K.shape[0]).T


def logistic_metrics(images, labels, t_images, t_labels):
    train_x = images[:30]
    train_y = labels[:30]
    test_x = t_images[:10000]
    test_y = t_labels[:10000]
    w = fit_logistic(train_x, train_y)

    # likelihood
    ll = np.multiply(train_y, pred_ll(train_x, w))
    test_ll = np.multiply(test_y, pred_ll(test_x, w))

    # accuracy
    pred = pred_ll(train_x, w)
    test_pred = pred_ll(test_x, w)
    print("average predictive log ll for training set is:")
    print(np.sum(ll)/30)
    print("average predictive log ll for test set is:")
    print(np.sum(test_ll)/10000)

    print("average predictive accuracy for training set is:")
    print(predictive_accuracy(pred, train_y))
    print("average predictive accuracy for test set is:")
    print(predictive_accuracy(test_pred, test_y))

    return w


def logistic_metrics_map(images, labels, t_images, t_labels, sigma):
    train_x = images[:30]
    train_y = labels[:30]
    test_x = t_images[:10000]
    test_y = t_labels[:10000]
    w = fit_logistic_map(train_x, train_y, sigma)

    # likelihood
    ll = np.multiply(train_y, pred_ll(train_x, w))
    test_ll = np.multiply(test_y, pred_ll(test_x, w))

    # accuracy
    pred = pred_ll(train_x, w)
    test_pred = pred_ll(test_x, w)
    print("average predictive log ll for training set is:")
    print(np.sum(ll)/30)
    print("average predictive log ll for test set is:")
    print(np.sum(test_ll)/10000)

    print("average predictive accuracy for training set is:")
    print(predictive_accuracy(pred, train_y))
    print("average predictive accuracy for test set is:")
    print(predictive_accuracy(test_pred, test_y))

    return w


def predictive_accuracy(proposed, true):
    return np.sum(np.equal(np.argmax(proposed, axis=1), np.argmax(true, axis=1)))/true.shape[0] * 100


if __name__ == '__main__':
    reader = data_reader()
    # saver = image_saver()
    n, a, b, c, d = reader.load_mnist()
    #
    a = np.round(a)
    c = np.round(c)
    a = a[:10000]
    b = b[:10000]
    c = c[:5000]
    d = d[:5000]
    # variational_optimization(a, b, c, d, num_iters=5001, sigma=10)
    # w = logistic_metrics_map(a,b,c,d, 10)
    # save_images(w, "1ce1")
    labeler = NoisyLabeler(a, b, c, d)
    labeler.power_level()
    labeler.get_noisy_train_valid()
