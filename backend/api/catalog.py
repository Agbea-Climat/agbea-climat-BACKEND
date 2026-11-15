from fastapi import APIRouter

from backend.schemas import ApiResponse, Dataset, Indicator, MapLayer, Mode, ok
from backend.services import catalog

router = APIRouter(tags=["catalog"])


@router.get("/indicators", response_model=ApiResponse[list[Indicator]])
def list_indicators():
    return ok(catalog.list_indicators())


@router.get("/datasets", response_model=ApiResponse[list[Dataset]])
def list_datasets():
    return ok(catalog.list_datasets())


@router.get("/datasets/{dataset_id}", response_model=ApiResponse[Dataset])
def get_dataset(dataset_id: str):
    return ok(catalog.get_dataset(dataset_id))


@router.get("/layers", response_model=ApiResponse[list[MapLayer]])
def list_layers(mode: Mode = "public"):
    return ok(catalog.list_layers(mode))
