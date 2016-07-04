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

'''
Python module of NeuroM to check neuronal trees.
'''

import numpy as np
from itertools import ifilter
from neurom.core.dataformat import COLS
from neurom.analysis import morphmath as mm
from neurom.analysis.morphmath import principal_direction_extent


def is_monotonic(neurite, tol):
    '''Check if neurite tree is monotonic, i.e. if each child has smaller or
        equal diameters from its parent

    Arguments:
        neurite : tree object
        tol: numerical precision
    '''

    for node in neurite.iter_nodes():
        # check that points in section satisfy monotonicity
        sec = node.value
        for point_id in xrange(len(sec) - 1):
            if sec[point_id + 1][COLS.R] > sec[point_id][COLS.R] + tol:
                return False
        # Check that section boundary points satisfy monotonicity
        if node.parent is not None:
            if sec[0][COLS.R] > node.parent.value[-1][COLS.R] + tol:
                return False

    return True


def is_flat(neurite, tol, method='tolerance'):
    '''Check if neurite is flat using the given method

    Input:
        neurite : the neurite tree object
        tol : tolerance
        method : the method of flatness estimation. 'tolerance'
        returns true if any extent of the tree
        is smaller than the given tolerance
        'ratio' returns true if the ratio of the smallest directions
        is smaller than tol. e.g. [1,2,3] -> 1/2 < tol

    Returns:
            True if it is flat

    '''

    ext = principal_direction_extent(neurite.points[:, :3])

    if method == 'ratio':
        sorted_ext = np.sort(ext)
        return sorted_ext[0] / sorted_ext[1] < float(tol)
    else:
        return any(ext < float(tol))


def is_back_tracking(neurite):
    ''' Check if a neurite process backtracks to a previous node. As back-tracking is taking place
    when a daughter of a branching process goes back and either overlaps with a previous point, or
    lies inside the cylindrical volume of the latter. This takes place in the lifetime of a single
    section and does not account for long backtracks where a tree might come back to itself.

    The algorithm checks if each segment in a section overlaps with all the previous ones. This
    is achieved by calculating the projection from the center of a segment to the endpoint of a pre
    vious one and by extension its complement, which has to be smaller that the sum of the radii
    of the segments combined with the norm of the projection being smaller than half of the segment
    length (distance is calculated from the center of the segment).

    Returns:
        True Under the following scenaria:
            1. A segment endpoint falls back and overlaps with a previous segment's point
            2. The geometry of a segment overlaps with a previous one in the section
    '''
    def pair(segs):
        ''' Pairs the input list into triplets
        '''
        return zip(segs, segs[1:])

    def coords(node):
        ''' Returns the first three values of the tree that
        correspond to the x, y, z coordinates
        '''
        return node[:COLS.R]

    def max_radius(seg):
        ''' Returns maximum radius from the two segment endpoints
        '''
        return max(seg[0][COLS.R], seg[1][COLS.R])

    def is_not_zero_seg(seg):
        ''' Returns True if segment has zero length
        '''
        return not np.allclose(coords(seg[0]), coords(seg[1]))

    def is_in_the_same_verse(seg1, seg2):
        ''' Checks if the vectors face the same direction. This
        is true if their dot product is greater than zero.
        '''
        v1 = coords(seg2[1]) - coords(seg2[0])
        v2 = coords(seg1[1]) - coords(seg1[0])
        return np.dot(v1, v2) >= 0

    def is_seg2_within_seg1_radius(dist, seg1, seg2):
        ''' Checks whether the orthogonal distance from the point at the end of
        seg1 to seg2 segment body is smaller than the sum of their radii
        '''
        return dist <= max_radius(seg1) + max_radius(seg2)

    def is_seg1_overlapping_with_seg2(seg1, seg2):
        '''Checks if a segment is in proximity of another one upstream
        '''
        # get the coordinates of seg2 (from the origin)
        s1 = coords(seg2[0])
        s2 = coords(seg2[1])

        # vector of the center of seg2 (from the origin)
        C = 0.5 * (s1 + s2)

        # endpoint of seg1 (from the origin)
        P = coords(seg1[1])

        # vector from the center C of seg2 to the endpoint P of seg1
        CP = P - C

        # vector of seg2
        S1S2 = s2 - s1

        # projection of CP upon seg2
        prj = mm.vector_projection(CP, S1S2)

        # check if the distance of the orthogonal complement of CP projection on S1S2
        # (vertical distance from P to seg2) is smaller than the sum of the radii. (overlap)
        # If not exit early, because there is no way that backtracking can feasible
        if not is_seg2_within_seg1_radius(np.linalg.norm(CP - prj), seg1, seg2):
            return False

        # projection lies within the length of the cylinder. Check if the distance between
        # the center C of seg2 and the projection of the end point of seg1, P is smaller than
        # half of the others length plus a 5% tolerance
        return np.linalg.norm(prj) < 0.55 * np.linalg.norm(S1S2)

    def is_inside_cylinder(seg1, seg2):
        ''' Checks if seg2 approximately lies within a cylindrical volume of seg1.
        Two conditions must be satisfied:
            1. The two segments are not facing the same direction  (seg2 comes back to seg1)
            2. seg2 is overlaping with seg1
        '''
        return not is_in_the_same_verse(seg1, seg2) and is_seg1_overlapping_with_seg2(seg1, seg2)

    # filter out single segment sections
    for snode in ifilter(lambda snode: snode.value.shape[0] > 2, neurite.iter_nodes()):

        # group each section's points intro triplets
        segment_pairs = filter(is_not_zero_seg, pair(snode.value))

        # filter out zero length segments
        for i, seg1 in enumerate(segment_pairs[1:]):
            # check if the end point of the segment lies within the previous
            # ones in the current sectionmake
            for seg2 in segment_pairs[0: i + 1]:
                if is_inside_cylinder(seg1, seg2):
                    return True
    return False
