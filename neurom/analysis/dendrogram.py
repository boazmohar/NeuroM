# Copyright (c) 2015, Ecole Polytechnique Federale de Lausanne, Blue Brain Project
# All rights reserved.
#
# This file is part of NeuroM <https://github.com/BlueBrain/NeuroM>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     1. Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#     2. Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#     3. Neither the name of the copyright holder nor the names of
#        its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''Dendrogram helper functions and class'''

from neurom.core.tree import Tree
from neurom.core.neuron import Neuron
from neurom.analysis.morphtree import n_segments, n_bifurcations, n_terminations
from neurom.analysis.morphmath import segment_length
from neurom.core.dataformat import COLS

from neurom.view import common
from matplotlib.collections import PolyCollection

import numpy as np
import sys


def _total_rectangles(tree):
    '''
    Calculate the total number of segments that are required
    for the dendrogram. There is a vertical line for each segment
    and two horizontal line at each branching point
    '''
    return n_segments(tree) + n_bifurcations(tree) * 2


def _n_rectangles(obj):
    '''
    Calculate the total number of rectangles with respect to
    the type of the object
    '''
    if isinstance(obj, Tree):

        return _total_rectangles(obj)

    elif isinstance(obj, Neuron):

        return sum([_total_rectangles(neu) for neu in obj.neurites])

    else:

        return 0


def displace(rectangles, t):
    '''Displace the collection of rectangles
    '''
    n, m, _ = rectangles.shape

    for i in xrange(n):

        for j in xrange(m):

            rectangles[i, j, 0] += t[0]
            rectangles[i, j, 1] += t[1]


def _vertical_segment(old_offs, new_offs, spacing, radii):
    '''Vertices fo a vertical rectangle
    '''
    return np.array(((new_offs[0] - radii[0], old_offs[1] + spacing[1]),
                     (new_offs[0] - radii[1], new_offs[1]),
                     (new_offs[0] + radii[1], new_offs[1]),
                     (new_offs[0] + radii[0], old_offs[1] + spacing[1])))


def _horizontal_segment(old_offs, new_offs, spacing, diameter):
    '''Vertices of a horizontal rectangle
    '''
    return np.array(((old_offs[0], old_offs[1] + spacing[1]),
                     (new_offs[0], old_offs[1] + spacing[1]),
                     (new_offs[0], old_offs[1] + spacing[1] - diameter),
                     (old_offs[0], old_offs[1] + spacing[1] - diameter)))


def _spacingx(node, max_dims, xoffset, xspace):
    '''Determine the spacing of the current node depending on the number
       of the leaves of the tree
    '''
    x_spacing = n_terminations(node) * xspace

    if x_spacing > max_dims[0]:
        max_dims[0] = x_spacing

    return xoffset - x_spacing / 2.


def _update_offsets(start_x, spacing, terminations, offsets, length):
    '''Update the offsets
    '''
    return (start_x + spacing[0] * terminations / 2.,
            offsets[1] + spacing[1] * 2. + length)


class Dendrogram(object):
    '''Dendrogram
    '''

    def __init__(self, obj):
        '''Create dendrogram
        '''

        # input object, tree, or neuron
        self._obj = obj

        # counter/index for the storage of the rectangles.
        # it is updated recursively
        self._n = 0

        self.scale = 1.

        # the maximum lengths in x and y that is occupied
        # by a neurite. It is updated recursively.
        self._max_dims = [0., 0.]

        # trees store the segment collections for each neurite
        # separately
        self._trees = []

        # dims store the max dimensions for each neurite
        # essential for the displacement in the plotting
        self._dims = []

        # initialize the number of rectangles
        self._rectangles = np.zeros([_n_rectangles(self._obj), 4, 2])

        print "nlines : ", _n_rectangles(self._obj)

    def generate(self):
        '''Generate dendrogram
        '''

        sys.setrecursionlimit(100000)

        spacing = (40., 0.)

        offsets = (0., 0.)

        n_previous = 0

        if isinstance(self._obj, Tree):

            self._generate_dendro(self._obj, spacing, offsets)

            self._trees = [self._rectangles]

        else:

            n_previous = 0

            for neurite in self._obj.neurites:

                self._generate_dendro(neurite, spacing, offsets)

                # store in trees the sliced array of lines for each neurite
                self._trees.append(self._rectangles[n_previous: self._n])

                # store the max dims per neurite for view positioning
                self._dims.append(self._max_dims)

                # reset the max dimensions for the next tree in line
                self._max_dims = [0., 0.]

                # keep track of the next tree start index in list
                n_previous = self._n

    @property
    def data(self):
        ''' data
        '''
        return self._rectangles

    def _generate_dendro(self, current_node, spacing, offsets):
        '''Recursive function for dendrogram line computations
        '''
        max_dims = self._max_dims
        start_x = _spacingx(current_node, max_dims, offsets[0], spacing[0])

        radii = [0., 0.]
        # store the parent radius in order to construct polygonal segments
        # isntead of simple line segments
        radii[0] = current_node.value[COLS.R] * self.scale

        for child in current_node.children:

            # segment length
            ln = segment_length((current_node.value, child.value))

            # extract the radius of the child node. Need both radius for
            # realistic segment representation
            radii[1] = child.value[COLS.R] * self.scale

            # number of leaves in child
            terminations = n_terminations(child)

            # horizontal spacing with respect to the number of
            # terminations
            new_offsets = _update_offsets(start_x, spacing, terminations, offsets, ln)

            # create and store vertical segment
            self._rectangles[self._n] = _vertical_segment(offsets, new_offsets, spacing, radii)

            # assign segment id to color array
            # colors[n[0]] = child.value[4]
            self._n += 1

            if offsets[1] + spacing[1] * 2 + ln > max_dims[1]:
                max_dims[1] = offsets[1] + spacing[1] * 2. + ln

            self._max_dims = max_dims
            # recursive call to self.
            self._generate_dendro(child, spacing, new_offsets)

            # update the starting position for the next child
            start_x += terminations * spacing[0]

            # write the horizontal lines only for bifurcations, where the are actual horizontal
            # lines and not zero ones
            if offsets[0] != new_offsets[0]:

                # horizontal segment
                self._rectangles[self._n] = _horizontal_segment(offsets, new_offsets, spacing, 0.)
                # colors[self._n] = current_node.value[4]
                self._n += 1

    def view(self, new_fig=True, subplot=None, **kwargs):
        '''
        Dendrogram Viewer
        '''

        def _format_str(string):
            ''' string formatting
            '''
            return string.replace('TreeType.', '').replace('_', ' ').capitalize()

        fig, ax = common.get_figure(new_fig=new_fig, subplot=subplot)

        displacement = 0.
        colors = set()

        for i, group in enumerate(self._trees):

            if i > 0:
                displacement += 0.5 * (self._dims[i - 1][0] + self._dims[i][0])

            # arrange the trees without overlapping with each other
            displace(group, (displacement, 0.))

            # color
            tree_type = self._obj.neurites[i].type

            color = common.TREE_COLOR[tree_type]

            # generate segment collection
            collection = PolyCollection(group, closed=False, antialiaseds=True,
                                        edgecolors=color, facecolors=color)

            # add it to the axes
            ax.add_collection(collection)

            # dummy plot for the legend
            if color not in colors:
                ax.plot((0., 0.), (0., 0.), c=color, label=_format_str(str(tree_type)))
                colors.add(color)

        ax.autoscale(enable=True, tight=None)

        # customization settings
        # kwargs['xticks'] = []
        kwargs['title'] = kwargs.get('title', 'Morphology Dendrogram')
        kwargs['xlabel'] = kwargs.get('xlabel', '')
        kwargs['ylabel'] = kwargs.get('ylabel', '')
        kwargs['no_legend'] = False

        return common.plot_style(fig=fig, ax=ax, **kwargs)
