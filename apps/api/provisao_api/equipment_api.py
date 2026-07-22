"""Catalog and customer equipment endpoints."""
from typing import Callable
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Customer, Equipment, EquipmentAccessory, EquipmentBrand, EquipmentCategory, EquipmentModel, User

def db():
    session=SessionLocal()
    try: yield session
    finally: session.close()

class CatalogPayload(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: str=Field(min_length=2,max_length=120)

class ModelPayload(BaseModel):
    model_config=ConfigDict(extra="forbid")
    name: str=Field(min_length=2,max_length=120); category_id: str|None=None; brand_id: str|None=None; specifications: dict = Field(default_factory=dict)

class EquipmentPayload(BaseModel):
    model_config=ConfigDict(extra="forbid")
    customer_id: str; contact_id: str|None=None; address_id: str|None=None; category_id: str|None=None; brand_id: str|None=None; model_id: str|None=None
    category: str=Field(min_length=2,max_length=100); manufacturer: str|None=None; model: str|None=None; serial_number: str|None=None; asset_number: str|None=None
    installation_date: datetime|None=None; purchase_date: datetime|None=None; warranty_until: datetime|None=None; status: str=Field(default="active",pattern="^(active|inactive|retired|in_repair)$"); location: str|None=None; technical_data: dict=Field(default_factory=dict); notes: str|None=None

class AccessoryPayload(BaseModel):
    description: str=Field(min_length=2,max_length=200); quantity: int=Field(default=1,ge=1,le=10000); condition: str|None=None; observation: str|None=None

def build_router(current_user: Callable, require: Callable, audit: Callable) -> APIRouter:
    router=APIRouter(prefix="/api/v1/equipment",tags=["equipment"])
    def owned_customer(session,user,id):
        item=session.scalar(select(Customer).where(Customer.id==id,Customer.company_id==user.company_id))
        if not item: raise HTTPException(404,"customer not found")
        return item
    def catalog(entity,user,session,id):
        item=session.scalar(select(entity).where(entity.id==id,entity.company_id==user.company_id))
        if not item: raise HTTPException(404,"catalog item not found")
        return item
    @router.get("/categories")
    def categories(user:User=Depends(current_user),session:Session=Depends(db)): return {"items":[{"id":x.id,"name":x.name,"active":x.active} for x in session.scalars(select(EquipmentCategory).where(EquipmentCategory.company_id==user.company_id).order_by(EquipmentCategory.name)).all()]}
    @router.post("/categories",status_code=201)
    def create_category(payload:CatalogPayload,user:User=Depends(require("equipment.create")),session:Session=Depends(db)):
        item=EquipmentCategory(company_id=user.company_id,name=payload.name);session.add(item);session.flush();audit(session,user,"equipment_category_created","equipment_category",item.id);session.commit();return {"id":item.id,"name":item.name}
    @router.get("/brands")
    def brands(user:User=Depends(current_user),session:Session=Depends(db)): return {"items":[{"id":x.id,"name":x.name,"active":x.active} for x in session.scalars(select(EquipmentBrand).where(EquipmentBrand.company_id==user.company_id).order_by(EquipmentBrand.name)).all()]}
    @router.post("/brands",status_code=201)
    def create_brand(payload:CatalogPayload,user:User=Depends(require("equipment.create")),session:Session=Depends(db)):
        item=EquipmentBrand(company_id=user.company_id,name=payload.name);session.add(item);session.flush();audit(session,user,"equipment_brand_created","equipment_brand",item.id);session.commit();return {"id":item.id,"name":item.name}
    @router.get("/models")
    def models(user:User=Depends(current_user),session:Session=Depends(db)): return {"items":[{"id":x.id,"name":x.name,"category_id":x.category_id,"brand_id":x.brand_id,"specifications":x.specifications or {}} for x in session.scalars(select(EquipmentModel).where(EquipmentModel.company_id==user.company_id).order_by(EquipmentModel.name)).all()]}
    @router.post("/models",status_code=201)
    def create_model(payload:ModelPayload,user:User=Depends(require("equipment.create")),session:Session=Depends(db)):
        if payload.category_id: catalog(EquipmentCategory,user,session,payload.category_id)
        if payload.brand_id: catalog(EquipmentBrand,user,session,payload.brand_id)
        item=EquipmentModel(company_id=user.company_id,**payload.model_dump());session.add(item);session.flush();audit(session,user,"equipment_model_created","equipment_model",item.id);session.commit();return {"id":item.id,"name":item.name}
    @router.get("")
    def equipment(q:str|None=None,customer_id:str|None=None,page:int=Query(1,ge=1),limit:int=Query(50,ge=1,le=100),user:User=Depends(current_user),session:Session=Depends(db)):
        statement=select(Equipment).where(Equipment.company_id==user.company_id).order_by(Equipment.created_at.desc()).offset((page-1)*limit).limit(limit)
        if customer_id: statement=statement.where(Equipment.customer_id==customer_id)
        if q: statement=statement.where(or_(Equipment.category.ilike(f"%{q[:100]}%"),Equipment.serial_number==q,Equipment.internal_code==q,Equipment.asset_number==q))
        return {"items":[equipment_view(x) for x in session.scalars(statement).all()],"page":page,"limit":limit}
    @router.post("",status_code=201)
    def create_equipment(payload:EquipmentPayload,user:User=Depends(require("equipment.create")),session:Session=Depends(db)):
        owned_customer(session,user,payload.customer_id)
        duplicate=session.scalar(select(Equipment).where(Equipment.company_id==user.company_id,or_(payload.serial_number and Equipment.serial_number==payload.serial_number,payload.asset_number and Equipment.asset_number==payload.asset_number))) if payload.serial_number or payload.asset_number else None
        if duplicate: raise HTTPException(409,detail={"message":"possible duplicate equipment","equipment_id":duplicate.id})
        data=payload.model_dump(); data["internal_code"]=f"EQ-{__import__('secrets').token_hex(5).upper()}"; item=Equipment(company_id=user.company_id,**data);session.add(item);session.flush();audit(session,user,"equipment_created","equipment",item.id);session.commit();return equipment_view(item)
    @router.get("/{equipment_id}")
    def get_equipment(equipment_id:str,user:User=Depends(current_user),session:Session=Depends(db)):
        item=session.scalar(select(Equipment).where(Equipment.id==equipment_id,Equipment.company_id==user.company_id))
        if not item: raise HTTPException(404,"equipment not found")
        accessories=session.scalars(select(EquipmentAccessory).where(EquipmentAccessory.equipment_id==item.id).order_by(EquipmentAccessory.description)).all()
        return {**equipment_view(item),"accessories":[accessory_view(x) for x in accessories]}
    @router.post("/{equipment_id}/accessories",status_code=201)
    def create_accessory(equipment_id:str,payload:AccessoryPayload,user:User=Depends(require("equipment.update")),session:Session=Depends(db)):
        item=session.scalar(select(Equipment).where(Equipment.id==equipment_id,Equipment.company_id==user.company_id))
        if not item: raise HTTPException(404,"equipment not found")
        accessory=EquipmentAccessory(company_id=user.company_id,equipment_id=item.id,**payload.model_dump());session.add(accessory);session.flush();audit(session,user,"equipment_accessory_added","equipment_accessory",accessory.id);session.commit();return accessory_view(accessory)
    return router

def equipment_view(item): return {"id":item.id,"customer_id":item.customer_id,"category":item.category,"manufacturer":item.manufacturer,"model":item.model,"serial_number":item.serial_number,"internal_code":item.internal_code,"asset_number":item.asset_number,"status":item.status,"location":item.location,"technical_data":item.technical_data or {},"notes":item.notes,"warranty_until":item.warranty_until}
def accessory_view(item): return {"id":item.id,"equipment_id":item.equipment_id,"description":item.description,"quantity":item.quantity,"condition":item.condition,"observation":item.observation,"returned":item.returned,"returned_at":item.returned_at}
