"""Contenu du site vitrine : pages d'édition (Secrétariat Information et Communication, administrateur),
fichiers déposés et données publiques lues à la reconstruction du site."""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import media, models, publish, site_content as sc
from ..audit import log_action
from ..database import get_db
from ..deps import require_content_editor
from ..web import render

router = APIRouter()

MAX_REQUEST_BYTES = 40 * 1024 * 1024


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _col(key: str) -> sc.Collection:
    col = sc.collection(key)
    if not col:
        raise HTTPException(status_code=404, detail="Rubrique introuvable")
    return col


def _item(db: Session, col: sc.Collection, item_id: int) -> models.ContenuSite:
    item = db.get(models.ContenuSite, item_id)
    if not item or item.collection != col.key:
        raise HTTPException(status_code=404, detail="Élément introuvable")
    return item


def _media_info(db: Session, col: sc.Collection, values: dict) -> dict:
    """Fichiers déjà liés à l'élément (pour les montrer dans le formulaire)."""
    info = {}
    for f in col.fields:
        raw = values.get(sc.form_name(f, "id"))
        if f.kind == "media" and raw and str(raw).isdigit():
            m = db.get(models.MediaSite, int(raw))
            if m:
                info[f.name] = m
    return info


def _form_page(request, user, db, col, *, item=None, values=None, errors=(), status_code=200):
    values = values if values is not None else (sc.flatten(col, sc.load(item)) if item else {})
    return render(request, "contenu_form.html", user, col=col, item=item, values=values, errors=list(errors),
                  medias=_media_info(db, col, values), status_code=status_code)


async def _read_form(request: Request, col: sc.Collection, db: Session, user: models.User) -> tuple[dict, list[str]]:
    """Valeurs du formulaire ; les fichiers déposés sont nettoyés puis enregistrés (annulés si une erreur survient)."""
    if int(request.headers.get("content-length") or 0) > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Envoi trop volumineux")
    form = await request.form()
    values = {k: v for k, v in form.items() if isinstance(v, str)}
    errors: list[str] = []
    for f in col.fields:
        if f.kind != "media":
            continue
        upload = form.get(sc.form_name(f, "file"))
        if upload is not None and not isinstance(upload, str) and upload.filename:
            try:
                data, mime, ext, digest = media.process(await upload.read(), f.media)
            except media.MediaError as e:
                errors.append(f"{f.label} : {e}")
                continue
            m = db.query(models.MediaSite).filter_by(sha256=digest).first()
            if not m:
                m = models.MediaSite(nom=media.safe_name(upload.filename), mime=mime, extension=ext, taille=len(data),
                                     sha256=digest, contenu=data, created_by_id=user.id)
                db.add(m)
                db.flush()
            values[sc.form_name(f, "id")] = str(m.id)
        elif values.get(sc.form_name(f, "clear")):
            values[sc.form_name(f, "id")] = ""
    return values, errors


def _validate(db: Session, col: sc.Collection, values: dict, upload_errors: list[str], current: models.ContenuSite | None):
    data, errors = sc.parse(col, values, lambda i: db.get(models.MediaSite, i))
    errors = upload_errors + errors
    key = None
    if not errors:
        errors += sc.check_collection_rules(col, data)
    if not errors:
        taken = {r.cle for r in db.query(models.ContenuSite).filter_by(collection=col.key)
                 if r.cle and not (current and r.id == current.id)}
        try:
            key = sc.make_key(col, data, taken)
        except sc.FormError as e:
            errors.append(str(e))
        if "slug" in data and key:
            data["slug"] = key
    return data, key, errors


def _published(db: Session, background: BackgroundTasks) -> None:
    sc.purge_unused_media(db)                 # une photo ou un PDF supprimé disparaît aussi de la base et du site
    db.commit()
    background.add_task(publish.trigger_rebuild)


@router.get("/gestion/contenu")
def content_index(request: Request, user: models.User = Depends(require_content_editor), db: Session = Depends(get_db)):
    counts = {c.key: db.query(models.ContenuSite).filter_by(collection=c.key).count() for c in sc.COLLECTIONS.values()}
    return render(request, "contenu_index.html", user, collections=sc.COLLECTIONS.values(), counts=counts,
                  auto_publish=publish.rebuild_configured())


@router.get("/gestion/contenu/{key}")
def content_list(key: str, request: Request, user: models.User = Depends(require_content_editor),
                 db: Session = Depends(get_db)):
    col = _col(key)
    rows = sc.items_of(db, key)
    if col.singleton:
        if not rows and (d := sc.default_values(col)):          # première ouverture : textes actuels du site
            return _form_page(request, user, db, col, values=sc.flatten(col, d))
        return _form_page(request, user, db, col, item=rows[0] if rows else None)
    entries = [(r, sc.title_of(col, sc.load(r))) for r in rows]
    return render(request, "contenu_liste.html", user, col=col, entries=entries,
                  can_import=bool(col.bloc and not rows and sc.default_values(col)))


@router.post("/gestion/contenu/{key}/importer")
def content_import_defaults(key: str, background: BackgroundTasks, user: models.User = Depends(require_content_editor),
                            db: Session = Depends(get_db)):
    """Crée les éléments d'une liste à partir des textes actuels du site, pour les corriger ensuite un par un."""
    col = _col(key)
    defaults = sc.default_values(col)
    if col.singleton or not defaults or sc.items_of(db, key):
        raise HTTPException(status_code=404, detail="Rubrique introuvable")
    for i, d in enumerate(defaults):
        row = models.ContenuSite(collection=key, position=i, data=json.dumps(d, ensure_ascii=False), updated_by_id=user.id)
        db.add(row)
    db.flush()
    log_action(db, user, "creation", f"contenu:{key}", None, f"import des textes actuels ({len(defaults)})")
    _published(db, background)
    return _redirect(f"/gestion/contenu/{key}?ok=1")


@router.get("/gestion/contenu/{key}/nouveau")
def content_new(key: str, request: Request, user: models.User = Depends(require_content_editor),
                db: Session = Depends(get_db)):
    col = _col(key)
    if col.singleton:
        return _redirect(f"/gestion/contenu/{key}")
    return _form_page(request, user, db, col)


async def _save(request, background, user, db, col, current):
    values, upload_errors = await _read_form(request, col, db, user)
    data, key, errors = _validate(db, col, values, upload_errors, current)
    if errors:
        db.rollback()
        return _form_page(request, user, db, col, item=current, values=values, errors=errors, status_code=400)
    if current is None:
        position = max((r.position for r in db.query(models.ContenuSite).filter_by(collection=col.key)), default=-1) + 1
        current = models.ContenuSite(collection=col.key, position=position, data="{}")
        db.add(current)
        action = "creation"
    else:
        action = "modification"
    current.cle, current.data, current.updated_by_id = key, json.dumps(data, ensure_ascii=False), user.id
    db.flush()
    log_action(db, user, action, f"contenu:{col.key}", current.id, sc.title_of(col, data)[:200])
    _published(db, background)
    return _redirect(f"/gestion/contenu/{col.key}?ok=1")


@router.post("/gestion/contenu/{key}/nouveau")
async def content_create(key: str, request: Request, background: BackgroundTasks,
                         user: models.User = Depends(require_content_editor), db: Session = Depends(get_db)):
    col = _col(key)
    if col.singleton:
        return _redirect(f"/gestion/contenu/{key}")
    return await _save(request, background, user, db, col, None)


@router.post("/gestion/contenu/{key}/unique")
async def content_save_single(key: str, request: Request, background: BackgroundTasks,
                              user: models.User = Depends(require_content_editor), db: Session = Depends(get_db)):
    col = _col(key)
    if not col.singleton:
        raise HTTPException(status_code=404, detail="Rubrique introuvable")
    rows = sc.items_of(db, key)
    return await _save(request, background, user, db, col, rows[0] if rows else None)


@router.get("/gestion/contenu/{key}/{item_id:int}/modifier")
def content_edit(key: str, item_id: int, request: Request, user: models.User = Depends(require_content_editor),
                 db: Session = Depends(get_db)):
    col = _col(key)
    return _form_page(request, user, db, col, item=_item(db, col, item_id))


@router.post("/gestion/contenu/{key}/{item_id:int}/modifier")
async def content_update(key: str, item_id: int, request: Request, background: BackgroundTasks,
                         user: models.User = Depends(require_content_editor), db: Session = Depends(get_db)):
    col = _col(key)
    return await _save(request, background, user, db, col, _item(db, col, item_id))


@router.post("/gestion/contenu/{key}/{item_id:int}/supprimer")
def content_delete(key: str, item_id: int, background: BackgroundTasks,
                   user: models.User = Depends(require_content_editor), db: Session = Depends(get_db)):
    col = _col(key)
    item = _item(db, col, item_id)
    log_action(db, user, "suppression", f"contenu:{col.key}", item.id, sc.title_of(col, sc.load(item))[:200])
    db.delete(item)
    _published(db, background)
    return _redirect(f"/gestion/contenu/{key}")


@router.post("/gestion/contenu/{key}/{item_id:int}/{direction}")
def content_move(key: str, item_id: int, direction: str, background: BackgroundTasks,
                 user: models.User = Depends(require_content_editor), db: Session = Depends(get_db)):
    if direction not in ("haut", "bas"):
        raise HTTPException(status_code=404, detail="Action inconnue")
    col = _col(key)
    rows = sc.items_of(db, key) if col.sort == "position" else []
    item = _item(db, col, item_id)
    if rows:
        order = [r.id for r in rows]
        i = order.index(item.id)
        j = i - 1 if direction == "haut" else i + 1
        if 0 <= j < len(order):
            order[i], order[j] = order[j], order[i]
            for pos, rid in enumerate(order):                 # positions renumérotées : plus d'ex æquo
                db.get(models.ContenuSite, rid).position = pos
            log_action(db, user, "ordre", f"contenu:{col.key}", item.id)
            _published(db, background)
    return _redirect(f"/gestion/contenu/{key}")


# ---------- Données publiques ----------

@router.get("/api/public/site.json")
def site_json(db: Session = Depends(get_db)):
    """Tout le contenu public du site vitrine, dans la forme de ses fichiers data/*.json.
    Lu par la construction du site ; jamais mis en cache longtemps pour qu'une modification se voie vite."""
    return JSONResponse(sc.export_site(db), headers={"Cache-Control": "public, max-age=60"})


@router.get("/medias/{filename}")
def media_file(filename: str, request: Request, db: Session = Depends(get_db)):
    stem, _, ext = filename.partition(".")
    if not stem.isdigit() or not ext:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    m = db.get(models.MediaSite, int(stem))
    if not m or m.extension != ext:
        raise HTTPException(status_code=404, detail="Fichier introuvable")
    etag = f'"{m.sha256[:32]}"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=31536000, immutable",
               "Content-Disposition": f'inline; filename="{m.nom}"'}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(m.contenu, media_type=m.mime, headers=headers)
