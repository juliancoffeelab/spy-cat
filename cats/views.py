import json

import requests
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .models import Cat, Mission, Target

MAX_CAT_MISSIONS = 3


def get_json(request: HttpRequest) -> dict:
    # ok, now I understand the value of DRF, lol
    data = json.loads(request.body)

    return data


# Create your views here.
def list_cats(request: HttpRequest) -> JsonResponse:
    cats = Cat.objects.all()
    return JsonResponse(
        {
            "cats": [
                {
                    "id": c.id,
                    "name": c.name,
                    "years_exp": c.experience,
                    "breed": c.breed,
                    "salary": c.salary,
                }
                for c in cats
            ]
        }
    )


@require_http_methods(["GET", "DELETE", "PATCH"])
@csrf_exempt
def cat(request: HttpRequest, cat_id: int) -> JsonResponse:
    if request.method == "GET":
        c = get_object_or_404(Cat, pk=cat_id)
        return JsonResponse(
            {
                "name": c.name,
                "years_exp": c.experience,
                "breed": c.breed,
                "salary": c.salary,
            }
        )
    elif request.method == "DELETE":
        Cat.objects.get(pk=cat_id).delete()
        return JsonResponse({"ok": cat_id})
    elif request.method == "PATCH":
        data = get_json(request)
        if set(data) != {"salary"}:
            return JsonResponse(
                {"err": "only salary can be changed"}, status=400
            )
        c = Cat.objects.get(pk=cat_id)

        new_salary = data["salary"]
        c.salary = new_salary
        c.save()
        return JsonResponse({"ok": cat_id, "new_salary": new_salary})
    else:
        raise RuntimeError("shouldn't be reachable")


def is_valid_breed(breed: str) -> bool:
    # TODO: we should probably cache this somehow
    r = requests.get("https://api.thecatapi.com/v1/breeds")
    breed_data = r.json()
    return breed in map(lambda data: data["name"], breed_data)


@require_POST
@csrf_exempt
# TODO: I guess this could be a PUT method?
# but then PUT should be idempotent and we create a new cat each time...
#
# this wouldn't be a problem if we had uniqueness constraint on name, I think
#
# or maybe I'm just overthinking
def create_cat(request: HttpRequest) -> JsonResponse:
    data = get_json(request)

    name = data["name"]
    experience = data["years_exp"]
    breed = data["breed"]
    if not is_valid_breed(breed):
        # TODO: move this check onto the model?
        #
        # how it is now, it's the only way where we're setting
        # the breed, but this could change, in theory
        #
        # and we'd need to pay attention to this everywhere
        return JsonResponse(
            {
                "err": "bad breed",
            },
            status=400,
        )

    salary = data["salary"]
    cat = Cat(name=name, experience=experience, breed=breed, salary=salary)
    cat.save()

    return JsonResponse({"id": cat.id})


def list_missions(request: HttpRequest) -> JsonResponse:
    missions = Mission.objects.all()
    return JsonResponse(
        {
            "missions": [
                {
                    "id": m.id,
                    "cat_id": m.cat.id if m.cat else None,
                    "complete": m.complete,
                    "targets": [
                        {
                            "target_id": t.id,
                            "name": t.name,
                            "country": t.country,
                            "notes": t.notes,
                            "complete": t.complete,
                        }
                        for t in m.target_set.all()
                    ],
                }
                for m in missions
            ]
        }
    )


@require_http_methods(["GET", "DELETE", "PATCH"])
def mission(request: HttpRequest, mission_id: int) -> JsonResponse:
    if request.method == "GET":
        m = get_object_or_404(Mission, pk=mission_id)
        return JsonResponse(
            {
                "id": m.id,
                "cat_id": m.cat.id if m.cat else None,
                "complete": m.complete,
                "targets": [
                    {
                        "target_id": t.id,
                        "name": t.name,
                        "country": t.country,
                        "notes": t.notes,
                        "complete": t.complete,
                    }
                    for t in m.target_set.all()
                ],
            }
        )
    elif request.method == "DELETE":
        Mission.objects.get(pk=mission_id).delete()
        return JsonResponse({"ok": mission_id})
    elif request.method == "PATCH":
        m = Mission.objects.get(pk=mission_id)
        data = get_json(request)
        if set(data) != {"cat_id"}:
            return JsonResponse({"err": "only cat can be changed"}, status=400)

        # NOTE: allows to un-assign cats
        # that's a feature, not a bug
        maybe_cat = None
        if (cat_id := data.get("cat_id")) is not None:
            # cat_id should already be int
            maybe_cat = get_object_or_404(Cat, pk=cat_id)
            # TODO: surely there must be some way to do it with ORM
            if maybe_cat.mission_set.count() >= MAX_CAT_MISSIONS:
                return JsonResponse(
                    {"err": f"cat already has {MAX_CAT_MISSIONS} jobs"},
                    status=400,
                )
        m.cat = maybe_cat
        m.save()

        return JsonResponse({"ok": mission_id, "new_cat": maybe_cat})
    else:
        raise RuntimeError("shouldn't be reachable")


@require_POST
@csrf_exempt
def create_mission(request: HttpRequest) -> JsonResponse:
    data = get_json(request)
    maybe_cat = None
    if (cat_id := data.get("cat_id")) is not None:
        maybe_cat = get_object_or_404(Cat, pk=cat_id)

    mission = Mission(cat=maybe_cat, complete=False)
    if (
        maybe_cat is not None
        and maybe_cat.mission_set.count() >= MAX_CAT_MISSIONS
    ):
        return JsonResponse(
            {"err": f"cat already has {MAX_CAT_MISSIONS} jobs"}, status=400
        )
    # save mission to able to link targets
    mission.save()

    for target in data["targets"]:
        mission.target_set.create(
            name=target["name"],
            country=target["country"],
            notes="",
            complete=False,
        )
    return JsonResponse({"id": mission.id})


@require_http_methods(["PATCH"])
@csrf_exempt
def target(request: HttpRequest, target_id: int) -> JsonResponse:
    data = get_json(request)
    if not (set(data) <= {"complete", "notes"}):
        return JsonResponse(
            {"err": "only 'complete' and 'notes' can be changed"}, status=400
        )
    t = get_object_or_404(Target, pk=target_id)
    if (notes := data.get("notes")) is not None:
        t.notes = notes
    if (status := data.get("complete")) is not None:
        t.complete = status
    t.save()
    return JsonResponse(
        {
            "ok": target_id,
            "name": t.name,
            "country": t.country,
            "notes": t.notes,
            "complete": t.complete,
            "mission_id": t.mission_id,
        }
    )
