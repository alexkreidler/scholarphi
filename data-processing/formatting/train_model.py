import os
import sys

import json

import torch
import numpy as np
import pandas as pd
import random
import cv2

# Some basic setup:
# Setup detectron2 logger
import detectron2
from detectron2.utils.logger import setup_logger
setup_logger()

# import some common detectron2 utilities
from detectron2 import model_zoo
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer
from detectron2.data import MetadataCatalog

from detectron2.structures import BoxMode
from detectron2.data import DatasetCatalog, MetadataCatalog

from detectron2.engine import DefaultTrainer
from detectron2.config import get_cfg

from detectron2.evaluation import COCOEvaluator, inference_on_dataset
from detectron2.data import build_detection_test_loader

from detectron2.modeling import build_model
from detectron2.checkpoint import DetectionCheckpointer

from detectron2.utils.visualizer import ColorMode


def get_box_dicts(img_dir):
    json_file = os.path.join(img_dir, "bounding_box_data.json")
    with open(json_file) as f:
        imgs_anns = json.load(f)

    dataset_dicts = []
    for idx, v in enumerate(imgs_anns.values()):
        record = {}
        
        filename = os.path.join(img_dir, v["filename"])
        height, width = cv2.imread(filename).shape[:2]
        
        record["file_name"] = filename
        record["image_id"] = idx
        record["height"] = height
        record["width"] = width
      
        annos = v["regions"]
        objs = []
        for _, anno in annos.items():
            assert not anno["region_attributes"]
            anno = anno["shape_attributes"]
            px = anno["all_points_x"]
            py = anno["all_points_y"]
            poly = [(x + 0.5, y + 0.5) for x, y in zip(px, py)]
            poly = [p for x in poly for p in x]

            obj = {
                "bbox": [np.min(px), np.min(py), np.max(px), np.max(py)],
                "bbox_mode": BoxMode.XYXY_ABS,
                "segmentation": [poly],
                "category_id": 0,
                "iscrowd": 0
            }
            objs.append(obj)
        record["annotations"] = objs
        dataset_dicts.append(record)
    return dataset_dicts


def visualize_model_predictions(Eqbox_metadata, img_dir, out_dir, Nsamp=300):
    
    dataset_dicts = get_box_dicts(img_dir)
    for d in random.sample(dataset_dicts, Nsamp):    
        im = cv2.imread(d["file_name"])
        outputs = predictor(im)
        v = Visualizer(im[:, :, ::-1],
                       metadata=Eqbox_metadata, 
                       scale=0.8, 
        )
        v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
        if not os.path.exists(out_dir):
            os.mkdir(out_dir)
        cv2.imwrite(os.path.join(out_dir, os.path.basename(d["file_name"])), v.get_image()[:, :, ::-1])

        
if __name__ == "__main__":
    CNN_data_dir = sys.argv[1]

    for d in ["train", "val"]:
        DatasetCatalog.register("Eqbox_" + d, lambda d=d: get_box_dicts(CNN_data_dir + d))
        MetadataCatalog.get("Eqbox_" + d).set(thing_classes=["Eqbox"])
    Eqbox_metadata = MetadataCatalog.get("Eqbox_train")

    cfg = get_cfg()
    cfg.merge_from_file(model_zoo.get_config_file("COCO-Detection/faster_rcnn_R_101_FPN_3x.yaml"))
    
    # train a model
    cfg.DATASETS.TRAIN = ("Eqbox_train",)
    cfg.DATASETS.TEST = ()
    cfg.DATALOADER.NUM_WORKERS = 1
    #cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url("COCO-Detection/faster_rcnn_R_101_FPN_3x.yaml")  # Let training initialize from model zoo
    cfg.SOLVER.IMS_PER_BATCH = 2
    cfg.SOLVER.BASE_LR = 0.0025  # pick a good LR
    #cfg.SOLVER.WEIGHT_DECAY = 0.0025 # L2 regularization
    cfg.SOLVER.MAX_ITER = 50 #3000 
    cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = 512  # faster, and good enough for this toy dataset (default: 512)
    cfg.MODEL.ROI_HEADS.NUM_CLASSES = 1  # only has one class (Eqbox)
    
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    trainer = DefaultTrainer(cfg)
    trainer.resume_or_load(resume=True)
    # If a thrid commandline argument is provided, only evaluate, don't train.
    if len(sys.argv) <= 2:
        trainer.train()

    # training performance evaluation:
    #cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth")
    #cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.7   # set the testing threshold for this model (adjusting gives a precision/recall tradeoff)
    #cfg.DATASETS.TEST = ("Eqbox_train", )
    #predictor = DefaultPredictor(cfg)
    #evaluator = COCOEvaluator("Eqbox_train", cfg, False, output_dir="./output_train/")
    #val_loader = build_detection_test_loader(cfg, "Eqbox_train")
    #inference_on_dataset(trainer.model, val_loader, evaluator)
    # another equivalent way is to use trainer.test

    # validation performance evaluation:
    cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth")
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.7   # set the testing threshold for this model (adjusting gives a precision/recall tradeoff)
    cfg.DATASETS.TEST = ("Eqbox_val", )
    predictor = DefaultPredictor(cfg)
    evaluator = COCOEvaluator("Eqbox_val", cfg, False, output_dir="./output_val/")
    val_loader = build_detection_test_loader(cfg, "Eqbox_val")
    model = build_model(cfg)
    torch.save(model.state_dict(), os.path.join(cfg.OUTPUT_DIR, "model_final_save.pth"))
    inference_on_dataset(trainer.model, val_loader, evaluator)
    # another equivalent way is to use trainer.test
    
    visualize_model_predictions(Eqbox_metadata, CNN_data_dir + 'val', CNN_data_dir + 'vis_val', Nsamp=10)

    
