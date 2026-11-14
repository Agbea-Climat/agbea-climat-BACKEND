from fastapi import APIRouter

from backend.schemas import Dataset, Indicator, MapLayer, Mode
from backend.services import catalog

router = APIRouter(tags=["catalog"])


@router.get("/indicators", response_model=list[Indicator])
def list_indicators():
    return catalog.list_indicators()


@router.get("/datasets", response_model=list[Dataset])
def list_datasets():
    return catalog.list_datasets()


@router.get("/datasets/{dataset_id}", response_model=Dataset)
def get_dataset(dataset_id: str):
    return catalog.get_dataset(dataset_id)


@router.get("/layers", response_model=list[MapLayer])
def list_layers(mode: Mode = "public"):
    return catalog.list_layers(mode)
