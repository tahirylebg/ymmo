"""Client space pages and form actions."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_client
from app.core.exceptions import DomainError
from app.core.formatting import euros
from app.models import User
from app.models.enums import PropertyCategory, PropertyType
from app.repositories.property_repository import CityRepository
from app.schemas.requests import EstimationCreate, OfferCreate, VisitCreate
from app.services.client_service import ClientService
from app.web.utils import parse_form, redirect, render

router = APIRouter(include_in_schema=False)
CurrentClient = Depends(require_client)


@router.get("/mon-espace")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = CurrentClient):
    return render(
        request, "client/dashboard.html", user, dashboard=ClientService(db).dashboard(user)
    )


@router.post("/biens/{property_id}/favori")
async def toggle_favorite(
    property_id: int, request: Request, db: Session = Depends(get_db), user: User = CurrentClient
):
    service = ClientService(db)
    if property_id in service.favorites.property_ids_for_user(user.id):
        service.remove_favorite(user, property_id)
        message = "Bien retiré de vos favoris."
    else:
        service.add_favorite(user, property_id)
        message = "Bien ajouté à vos favoris."
    back = (await request.form()).get("back") or f"/biens/{property_id}"
    return redirect(str(back) if str(back).startswith("/") else "/", message)


async def _submit(request: Request, schema, action, property_id: int, success: str, anchor: str):
    form = dict(await request.form())
    form["property_id"] = property_id
    data, errors = parse_form(schema, form)
    target = f"/biens/{property_id}#{anchor}"
    if data is None:
        return redirect(target, " ".join(errors.values()), level="error")
    try:
        action(data)
    except DomainError as exc:
        return redirect(target, exc.message, level="error")
    return redirect("/mon-espace", success)


@router.post("/biens/{property_id}/visite")
async def request_visit(
    property_id: int, request: Request, db: Session = Depends(get_db), user: User = CurrentClient
):
    service = ClientService(db)
    return await _submit(
        request,
        VisitCreate,
        lambda d: service.request_visit(user, d),
        property_id,
        "Votre demande de visite a été transmise à l'agent.",
        "visite",
    )


@router.post("/biens/{property_id}/offre")
async def make_offer(
    property_id: int, request: Request, db: Session = Depends(get_db), user: User = CurrentClient
):
    service = ClientService(db)
    return await _submit(
        request,
        OfferCreate,
        lambda d: service.make_offer(user, d),
        property_id,
        "Votre offre a été envoyée.",
        "offre",
    )


@router.post("/mon-espace/visites/{visit_id}/annuler")
def cancel_visit(visit_id: int, db: Session = Depends(get_db), user: User = CurrentClient):
    try:
        ClientService(db).cancel_visit(user, visit_id)
    except DomainError as exc:
        return redirect("/mon-espace#visites", exc.message, level="error")
    return redirect("/mon-espace#visites", "Visite annulée.")


@router.post("/mon-espace/offres/{offer_id}/retirer")
def withdraw_offer(offer_id: int, db: Session = Depends(get_db), user: User = CurrentClient):
    try:
        ClientService(db).withdraw_offer(user, offer_id)
    except DomainError as exc:
        return redirect("/mon-espace#offres", exc.message, level="error")
    return redirect("/mon-espace#offres", "Offre retirée.")


@router.post("/estimer")
async def submit_estimation(
    request: Request, db: Session = Depends(get_db), user: User = CurrentClient
):
    form = await request.form()
    data, errors = parse_form(EstimationCreate, form)
    if data is None:
        return render(
            request,
            "estimate.html",
            user,
            status_code=422,
            cities=CityRepository(db).list(limit=500),
            property_types=list(PropertyType),
            categories=list(PropertyCategory),
            values=dict(form),
            errors=errors,
        )
    estimation = ClientService(db).submit_estimation(user, data)
    return redirect(
        "/mon-espace#estimations",
        f"Demande envoyée. Estimation indicative : {euros(estimation.estimated_price)}. "
        "Un agent de l'agence la plus proche vous recontacte.",
    )
