"""

Taken and adapted from `https://github.com/allenai/deepequations2`

"""

import json
import logging
import os
import re
import sys
from functools import reduce
from typing import List, NamedTuple

import cv2
import numpy as np
from imageio import imread, imsave

from explanations.directories import (get_colorized_pdf_path,
                                      get_original_pdf_path)
from explanations.image_processing import (diff_image_lists, get_cv2_images,
                                           open_pdf)


class PdfBoundingBox(NamedTuple):
    left: float
    top: float
    width: float
    height: float
    page: int


def get_bounding_boxes(arxiv_id, pdf_name) -> List[PdfBoundingBox]:
    logging.debug("Getting bounding boxes for %s", pdf_name)

    original_pdf_path = get_original_pdf_path(arxiv_id, pdf_name)
    colorized_pdf_path = get_colorized_pdf_path(arxiv_id, pdf_name)
    original_images = get_cv2_images(original_pdf_path)
    colorized_images = get_cv2_images(colorized_pdf_path)
    image_diffs = diff_image_lists(original_images, colorized_images)

    pdf = open_pdf(original_pdf_path)
    pdf_bounding_boxes = []
    for page_index, image_diff in enumerate(image_diffs):
        logging.debug("Finding bounding boxes in page %d", page_index)
        bounding_boxes = find_bounding_boxes_for_page(image_diff)
        image_height, image_width, _ = image_diff.shape
        page = pdf[page_index]
        page_width = page.rect.width
        page_height = page.rect.height
        pdf_bounding_boxes.extend(
            [
                _to_pdf_coordinates(
                    box, image_width, image_height, page_width, page_height, page_index
                )
                for box in bounding_boxes
            ]
        )

    return pdf_bounding_boxes


def find_bounding_boxes_for_page(image_diff: np.array):
    connected_components = find_connected_components(
        image_diff, lower=np.array([0, 0, 0]), upper=np.array([180, 255, 125])
    )
    level, clusters, d = cluster_nearby_connected_components(connected_components)
    bounding_boxes = [merge_bbs(cluster) for cluster in clusters]
    return bounding_boxes


def _to_pdf_coordinates(
    bounding_box: List[int],
    image_width: int,
    image_height: int,
    pdf_page_width: float,
    pdf_page_height: float,
    page: int,
) -> PdfBoundingBox:
    left, top, right, bottom = bounding_box
    pdf_left = left * (pdf_page_width / image_width)
    pdf_right = right * (pdf_page_width / image_width)
    # PDF coordinates are relative to the document bottom; image coordinates are relative to the
    # image's top. Flip y-coordinates.
    pdf_top = pdf_page_height - (top * (pdf_page_height / image_height))
    pdf_bottom = pdf_page_height - (bottom * (pdf_page_height / image_height))
    return PdfBoundingBox(
        left=pdf_left,
        top=pdf_top,
        width=pdf_right - pdf_left,
        height=pdf_top - pdf_bottom,
        page=page,
    )


def _find_connected_components(img, lower, upper):
    selected = cv2.inRange(img, lower, upper)
    num_components, labels, stats, centroids = cv2.connectedComponentsWithStats(
        selected
    )
    for index, stat in enumerate(stats):
        minX = stat[0]
        minY = stat[1]
        maxX = minX + stat[2]
        maxY = minY + stat[3]
        yield (minX, minY, maxX, maxY)


def find_connected_components(img, lower, upper):
    gen = _find_connected_components(img, lower, upper)
    # Drop background bb.
    next(gen)
    return list(gen)


def width(bb):
    return bb[2] - bb[0]


def height(bb):
    return bb[3] - bb[1]


def merge_bbs(cluster):
    return reduce(merge_bb, cluster)


def merge_bb(bb0, bb1):
    return (
        min(bb0[0], bb1[0]),
        min(bb0[1], bb1[1]),
        max(bb0[2], bb1[2]),
        max(bb0[3], bb1[3]),
    )


# Takes bounding box tuples of the form (minX, minY, maxX, maxY).
# See https://gamedev.stackexchange.com/questions/154036/efficient-minimum-distance-between-two-axis-aligned-squares for details.
def min_squared_distance(bb0, bb1):
    outer_bb = merge_bb(bb0, bb1)
    inner_w = width(outer_bb) - width(bb0) - width(bb1)
    inner_h = height(outer_bb) - height(bb0) - height(bb1)
    clamped_inner_w = max(0, inner_w)
    clamped_inner_h = max(0, inner_h)
    return clamped_inner_w * clamped_inner_w + clamped_inner_h * clamped_inner_h


def get_d(i, j, d):
    if j < i:
        return d[j][i]
    else:
        return d[i][j]


def set_d(i, j, d, val):
    if j < i:
        d[j][i] = val
    else:
        d[i][j] = val


# Returns (level, new_clusters, new_d).
def cluster_closest(clusters, d):
    size = len(clusters)
    if len(clusters) < 2:
        raise Exception("Clusters must have length at least 2")

    # Arbitrary entry
    min_i = -1
    min_j = -1
    min_d = d[0][1]
    for i in range(size):
        for j in range(i + 1, size):
            d_scalar = get_d(i, j, d)
            if d_scalar <= min_d:
                min_i = i
                min_j = j
                min_d = d_scalar

    # Drop row and column for min_i and min_j.
    dropped_d = np.delete(np.delete(d, [min_i, min_j], 0), [min_i, min_j], 1)

    new_vals = []
    for cur in range(0, size):
        if cur == min_i or cur == min_j:
            continue
        new_vals.append(min(get_d(cur, min_i, d), get_d(cur, min_j, d)))
    new_vals.append(0)

    new_d = np.full((size - 1, size - 1), -999, dtype=int)
    new_d[: size - 2, : size - 2] = dropped_d
    new_d[:, size - 2] = new_vals

    # Fix up clusters
    new_clusters = clusters[:]
    # Delete j first as it's larger.
    del new_clusters[min_j]
    del new_clusters[min_i]
    new_clusters.append(clusters[min_i] | clusters[min_j])

    # Smooth level to avoid divide by 0.
    return (min_d + 1, new_clusters, new_d)


# Note: Don't pass the background bounding box.
def cluster_nearby_connected_components(bbs):
    bb_list = list(bbs)
    init_size = len(bb_list)
    prev_d = np.full((init_size, init_size), -999, dtype=int)

    # Smoothing. (A previous level of 0 would make a level of 1 look very bad.)
    prev_level = 1
    prev_clusters = [set([bb]) for bb in bb_list]
    # Init distance matrix.
    for i, bb0 in enumerate(bb_list):
        prev_d[i][i] = 0
        for j, bb1 in enumerate(bb_list):
            if j <= i:
                continue
            prev_d[i][j] = min_squared_distance(bb0, bb1)

    if len(prev_clusters) < 2:
        return (prev_level, prev_clusters, prev_d)
    new_level, new_clusters, new_d = cluster_closest(prev_clusters, prev_d)

    iteration = 0
    # Note: If we change the size of our images, we'll want to modify 200.
    # That's in squared pixels and was hand tuned to work on a 2480 × 3300
    # pixel image. (Big dataset trained with 50.)
    # Note: If you update this stopping condition, update in the if below too!!!
    while (new_level < 200 or new_level / prev_level < 2) and len(new_clusters) > 1:
        # print("iteration: {}".format(iteration))
        # print("new_level: {} prev_level: {}".format(new_level, prev_level))
        iteration += 1
        prev_level = new_level
        prev_clusters = new_clusters
        prev_d = new_d
        new_level, new_clusters, new_d = cluster_closest(prev_clusters, prev_d)

    # print("new level: {}, prev level: {}".format(new_level, prev_level)) #DELETEME

    # When there is a single final (good) cluster.
    if new_level < 200 or new_level / prev_level < 2:
        return (new_level, new_clusters, new_d)
    else:
        return (prev_level, prev_clusters, prev_d)


mainUpperScalar = 255
mainLowerScalar = 250
otherUpperScalar = 240
otherLowerScalar = 0


def lowerBgr(index):
    arr = np.full(3, otherLowerScalar)
    arr[index] = mainLowerScalar
    return arr


def upperBgr(index):
    arr = np.full(3, otherUpperScalar)
    arr[index] = mainUpperScalar
    return arr


def bbs_for_color(img, color_index):
    bbs = find_connected_components(img, lowerBgr(color_index), upperBgr(color_index))
    # print("num bbs: {}".format(len(bbs))) #DELETEME
    if len(bbs) > 500:
        return (False, [])
    level, clusters, d = cluster_nearby_connected_components(bbs)
    # print("num clusters: {}".format(len(clusters))) #DELETEME
    return (True, [merge_bbs(cluster) for cluster in clusters])


def bb_to_dict(bb):
    minX, minY, maxX, maxY = bb
    return {
        "p_min": {"x": int(minX), "y": int(minY)},
        "p_max": {"x": int(maxX), "y": int(maxY)},
    }


# Accepts the prefix of the filename for the png. This should correspond
# minimally to $PREFIX-dif.png and $PREFIX-raw.png.
too_many_bbs = 0


def process_image(filename_prefix):
    global too_many_bbs
    img = imread("{}-dif.png".format(filename_prefix))
    raw_img = imread("{}-raw.png".format(filename_prefix))

    blue_status, blue_bbs = bbs_for_color(img, 0)
    green_status, green_bbs = bbs_for_color(img, 1)
    red_status, red_bbs = bbs_for_color(img, 2)

    dicts = []
    if not blue_status or not green_status or not red_status:
        print("too many bbs file: {}".format(filename_prefix))
        too_many_bbs += 1
        return dicts

    label_bbs = blue_bbs
    for i, label_bb in enumerate(label_bbs):
        label_dict = {
            "boundingBox": bb_to_dict(label_bb),
            "class": "label",
            "id": "label_{}".format(i),
        }
        dicts.append(label_dict)
        minX, minY, maxX, maxY = label_bb
        cv2.rectangle(raw_img, (minX, minY), (maxX, maxY), (255, 0, 0))

    equation_bbs = green_bbs + red_bbs
    for i, equation_bb in enumerate(equation_bbs):
        equation_dict = {
            "boundingBox": bb_to_dict(equation_bb),
            "class": "equation",
            "id": "equation_{}".format(i),
        }
        dicts.append(equation_dict)
        minX, minY, maxX, maxY = equation_bb
        cv2.rectangle(raw_img, (minX, minY), (maxX, maxY), (0, 255, 0))

    return dicts
