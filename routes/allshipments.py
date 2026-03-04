from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os
import datetime
from typing import Optional

# Auth dependencies
from core.auth import get_required_current_user, get_current_admin_user

# Load .env variables
load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# MongoDB connection
client = MongoClient(os.getenv("MONGO_URI"))
db = client['projectfast']
shipments_collection = db['shipments']

@router.get("/myshipment")
async def allshipments(
    request: Request,
    user=Depends(get_required_current_user)
):
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")

    query = {"created_by": user_email}
    shipments = list(shipments_collection.find(query))
    for shipment in shipments:
        shipment["_id"] = str(shipment["_id"])

    return templates.TemplateResponse("allshipments.html", {
        "request": request,
        "shipments": shipments,
        "created_by": user_email,
        "is_admin": False  # Always false since admin access is disabled
    })


@router.get("/allshipment")
async def allshipments(
    request: Request,
    created_by: Optional[str] = Query(None),
    user=Depends(get_required_current_user)
):
    user_email = user.get("email")
    user_role = user.get("role")

    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")

    # Build query based on role
    if user_role == "admin":
        # Admin can filter by any email or see all
        query = {}
        if created_by:
            query["created_by"] = {"$regex": f"^{created_by}", "$options": "i"}
    else:
        # Regular users can only see their own shipments
        query = {"created_by": user_email}

    shipments = list(shipments_collection.find(query))
    for shipment in shipments:
        shipment["_id"] = str(shipment["_id"])

    return templates.TemplateResponse("allshipments.html", {
        "request": request,
        "shipments": shipments,
        "created_by": created_by or (user_email if user_role != "admin" else ""),
        "is_admin": user_role == "admin"
    })


@router.get("/editshipment/{shipment_id}")
async def edit_shipment_form(
    request: Request,
    shipment_id: str,
    user: dict = Depends(get_required_current_user),
    admin_user: Optional[dict] = Depends(get_current_admin_user)
):
    """Allow editing only if user created the shipment or is admin"""
    query = {"_id": ObjectId(shipment_id)}
    
    # Regular users can only edit their own shipments
    if not admin_user:
        query["created_by"] = user["email"]

    shipment = shipments_collection.find_one(query)
    
    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found or not authorized"
        )
    
    shipment['_id'] = str(shipment['_id'])
    return templates.TemplateResponse("editshipment.html", {
        "request": request,
        "shipment": shipment,
        "is_admin": admin_user is not None
    })

@router.post("/editshipment/{shipment_id}")
async def update_shipment(
    shipment_id: str,
    request: Request,
    shipment_number: str = Form(...),
    route: str = Form(...),
    device: str = Form(...),
    po_number: int = Form(...),
    ndc_number: int = Form(...),
    serial_number: int = Form(...),
    goods_type: str = Form(...),
    expected_delivery_date: str = Form(...),
    delivery_number: int = Form(...),
    batch_id: str = Form(...),
    shipment_description: str = Form(...),
    user: dict = Depends(get_required_current_user),
    admin_user: Optional[dict] = Depends(get_current_admin_user)
):
    """Update shipment only if user created it or is admin"""
    query = {"_id": ObjectId(shipment_id)}
    
    if not admin_user:
        query["created_by"] = user["email"]

    # Verify shipment exists and user has permission
    existing_shipment = shipments_collection.find_one(query)
    if not existing_shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found or not authorized"
        )

    # Perform the update
    result = shipments_collection.update_one(
        query,
        {"$set": {
            "shipmentNumber": shipment_number,
            "route": route,
            "device": device,
            "poNumber": po_number,
            "ndcNumber": ndc_number,
            "serialNumber": serial_number,
            "goodsType": goods_type,
            "expected_delivery_date": expected_delivery_date,
            "deliveryNumber": delivery_number,
            "batchId": batch_id,
            "shipmentDesc": shipment_description,
            "updated_by": user["email"],  # Track who made the change
            "updated_at": datetime.datetime.now()
        }}
    )
    
    return RedirectResponse(url="/allshipment", status_code=303)

@router.post("/deleteshipments")
async def delete_selected_shipments(
    request: Request,
    user: dict = Depends(get_required_current_user),
    admin_user: Optional[dict] = Depends(get_current_admin_user)
):
    """Delete shipments only if user created them or is admin"""
    form_data = await request.form()
    selected_ids = form_data.getlist("selected_shipments")
    
    if not selected_ids:
        return RedirectResponse("/allshipment", status_code=303)
    
    for sid in selected_ids:
        query = {"_id": ObjectId(sid)}
        
        if not admin_user:
            query["created_by"] = user["email"]
        
        shipments_collection.delete_one(query)
    
    return RedirectResponse("/allshipment", status_code=303)

