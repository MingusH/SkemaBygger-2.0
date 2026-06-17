from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate, RoomRead
from app.routers._deps import require_school_admin, require_school_member

router = APIRouter(prefix="/schools/{school_id}/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomRead])
def list_rooms(school_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    return db.query(Room).filter(Room.school_id == school_id).all()


@router.post("", response_model=RoomRead, status_code=201)
def create_room(school_id: int, body: RoomCreate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    room = Room(school_id=school_id, **body.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/{room_id}", response_model=RoomRead)
def get_room(school_id: int, room_id: int, db: Session = Depends(get_db), _=Depends(require_school_member)):
    room = db.query(Room).filter(Room.id == room_id, Room.school_id == school_id).first()
    if not room:
        raise HTTPException(404, "Room not found")
    return room


@router.patch("/{room_id}", response_model=RoomRead)
def update_room(school_id: int, room_id: int, body: RoomUpdate, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    room = db.query(Room).filter(Room.id == room_id, Room.school_id == school_id).first()
    if not room:
        raise HTTPException(404, "Room not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(room, k, v)
    db.commit()
    db.refresh(room)
    return room


@router.delete("/{room_id}", status_code=204)
def delete_room(school_id: int, room_id: int, db: Session = Depends(get_db), _=Depends(require_school_admin)):
    room = db.query(Room).filter(Room.id == room_id, Room.school_id == school_id).first()
    if not room:
        raise HTTPException(404, "Room not found")
    db.delete(room)
    db.commit()
