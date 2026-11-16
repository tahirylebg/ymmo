"""Back-office pages: dashboard, listing management, visits, offers, sales, estimations."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_staff
from app.core.exceptions import DomainError
from app.models import User
from app.models.enums import PropertyCategory, PropertyStatus, PropertyType, UserRole
from app.repositories.property_repository import AgencyRepository, CityRepository
from app.schemas.property import PropertyCreate, PropertyUpdate
from app.schemas.staff import EstimationConversion, TransactionCreate
from app.services.property_service import PropertyService
from app.services.staff_service import StaffService
from app.web.utils import parse_form, redirect, render

router = APIRouter(prefix="/back-office", include_in_schema=False)
Staff = Depends(require_staff)


def _form_context(db: Session, user: User) -> dict:
    agencies = AgencyRepository(db).all() if user.role == UserRole.ADMIN else []
    return {
        "cities": CityRepository(db).list(limit=500),
        "agencies": agencies,
        "property_types": list(PropertyType),
        "categories": list(PropertyCategory),
        "statuses": list(PropertyStatus),
    }


def _attempt(action: Callable[[], object], target: str, success: str):
    """Run a domain action and redirect with a success or error flash message (DRY)."""
    try:
        action()
    except DomainError as exc:
        return redirect(target, exc.message, level="error")
    return redirect(target, success)


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Staff):
    return render(request, "staff/dashboard.html", user, board=StaffService(db).dashboard(user))


# --- Listings ------------------------------------------------------------------------------
@router.get("/biens/nouveau")
def new_property(request: Request, db: Session = Depends(get_db), user: User = Staff):
    return render(
        request,
        "staff/property_form.html",
        user,
        prop=None,
        values={},
        errors={},
        **_form_context(db, user),
    )


@router.post("/biens/nouveau")
async def create_property(request: Request, db: Session = Depends(get_db), user: User = Staff):
    form = await request.form()
    data, errors = parse_form(PropertyCreate, form)
    if data is not None:
        try:
            prop = PropertyService(db).create(data, user)
            return redirect(
                f"/back-office/biens/{prop.id}",
                f"Bien {prop.reference} publié. Ajoutez maintenant des photos.",
            )
        except DomainError as exc:
            errors = {"__all__": exc.message}
    return render(
        request,
        "staff/property_form.html",
        user,
        status_code=422,
        prop=None,
        values=dict(form),
        errors=errors,
        **_form_context(db, user),
    )


@router.get("/biens/{property_id}")
def edit_property(
    property_id: int, request: Request, db: Session = Depends(get_db), user: User = Staff
):
    service = PropertyService(db)
    prop = service.get_managed(property_id, user)
    staff = StaffService(db)
    return render(
        request,
        "staff/property_form.html",
        user,
        prop=prop,
        values={},
        errors={},
        offers=staff.offers.for_property(prop.id),
        sale=staff.transactions.for_property(prop.id),
        views=service.properties.count_views(prop.id),
        **_form_context(db, user),
    )


@router.post("/biens/{property_id}")
async def update_property(
    property_id: int, request: Request, db: Session = Depends(get_db), user: User = Staff
):
    form = await request.form()
    data, errors = parse_form(PropertyUpdate, form)
    target = f"/back-office/biens/{property_id}"
    if data is None:
        return redirect(target, " ".join(errors.values()), level="error")
    return _attempt(
        lambda: PropertyService(db).update(property_id, data, user), target, "Annonce mise à jour."
    )


@router.post("/biens/{property_id}/statut")
def change_status(
    property_id: int,
    status: PropertyStatus = Form(...),
    db: Session = Depends(get_db),
    user: User = Staff,
):
    return _attempt(
        lambda: PropertyService(db).change_status(property_id, status, user),
        f"/back-office/biens/{property_id}",
        "Statut mis à jour.",
    )


@router.post("/biens/{property_id}/supprimer")
def delete_property(property_id: int, db: Session = Depends(get_db), user: User = Staff):
    try:
        PropertyService(db).delete(property_id, user)
    except DomainError as exc:
        return redirect(f"/back-office/biens/{property_id}", exc.message, level="error")
    return redirect("/back-office", "Annonce supprimée.")


@router.post("/biens/{property_id}/photos")
async def upload_photo(
    property_id: int,
    file: UploadFile = File(...),
    alt_text: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Staff,
):
    content = await file.read()
    return _attempt(
        lambda: PropertyService(db).add_photo(property_id, content, alt_text, user),
        f"/back-office/biens/{property_id}#photos",
        "Photo ajoutée.",
    )


@router.post("/biens/{property_id}/photos/{photo_id}/supprimer")
def delete_photo(
    property_id: int, photo_id: int, db: Session = Depends(get_db), user: User = Staff
):
    return _attempt(
        lambda: PropertyService(db).delete_photo(property_id, photo_id, user),
        f"/back-office/biens/{property_id}#photos",
        "Photo supprimée.",
    )


@router.post("/biens/{property_id}/vente")
async def conclude_sale(
    property_id: int, request: Request, db: Session = Depends(get_db), user: User = Staff
):
    data, errors = parse_form(TransactionCreate, await request.form())
    target = f"/back-office/biens/{property_id}#vente"
    if data is None:
        return redirect(target, " ".join(errors.values()), level="error")
    return _attempt(
        lambda: StaffService(db).conclude_sale(user, property_id, data),
        target,
        "Vente enregistrée. Félicitations !",
    )


# --- Visits, offers, estimations -----------------------------------------------------------
VISIT_ACTIONS = {
    "confirmer": ("confirm_visit", "Visite confirmée."),
    "effectuee": ("complete_visit", "Visite marquée comme effectuée."),
    "annuler": ("cancel_visit", "Visite annulée."),
}
OFFER_ACTIONS = {
    "accepter": ("accept_offer", "Offre acceptée : le bien passe sous offre."),
    "refuser": ("reject_offer", "Offre refusée."),
}
ESTIMATION_ACTIONS = {
    "prendre": ("review_estimation", "Demande prise en charge."),
    "refuser": ("reject_estimation", "Demande refusée."),
}


def _dispatch(actions: dict, action: str, db: Session, user: User, entity_id: int, back: str):
    if action not in actions:
        return redirect(back, "Action inconnue.", level="error")
    method, message = actions[action]
    service = StaffService(db)
    return _attempt(lambda: getattr(service, method)(user, entity_id), back, message)


@router.post("/visites/{visit_id}/{action}")
async def visit_action(
    visit_id: int, action: str, request: Request, db: Session = Depends(get_db), user: User = Staff
):
    return _dispatch(VISIT_ACTIONS, action, db, user, visit_id, "/back-office#visites")


@router.post("/offres/{offer_id}/{action}")
async def offer_action(
    offer_id: int, action: str, request: Request, db: Session = Depends(get_db), user: User = Staff
):
    back = str((await request.form()).get("back") or "/back-office#offres")
    return _dispatch(
        OFFER_ACTIONS, action, db, user, offer_id, back if back.startswith("/") else "/back-office"
    )


@router.post("/estimations/{estimation_id}/{action}")
async def estimation_action(
    estimation_id: int,
    action: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Staff,
):
    if action == "mandat":
        data, errors = parse_form(EstimationConversion, await request.form())
        if data is None:
            return redirect("/back-office#estimations", " ".join(errors.values()), level="error")
        try:
            prop = StaffService(db).convert_estimation(user, estimation_id, data)
        except DomainError as exc:
            return redirect("/back-office#estimations", exc.message, level="error")
        return redirect(f"/back-office/biens/{prop.id}", "Mandat signé : l'annonce est publiée.")
    return _dispatch(
        ESTIMATION_ACTIONS, action, db, user, estimation_id, "/back-office#estimations"
    )
