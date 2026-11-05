
import pytest
from rest_framework.test import APIClient

PROFILE_URL = "/api/resume/profile/"


@pytest.mark.django_db
def test_user_can_view_profile(api):
    response = api.get(PROFILE_URL)

    assert response.status_code == 200
    assert response.data["full_name"] == ""
    assert response.data["skills"] == ["Python", "PyTorch", "SQL", "Docker"]
    assert response.data["years_of_experience"] == 2


@pytest.mark.django_db
def test_user_can_update_profile(api):
    data = {
        "full_name": "Test User",
        "skills": ["Python", "Django", "SQL"],
        "years_of_experience": 3,
        "highest_qualification": "B.Tech",
        "preferred_roles": ["Backend Developer"],
        "preferred_locations": ["Bengaluru", "Hyderabad"],
    }

    response = api.put(PROFILE_URL, data, format="json")

    assert response.status_code == 200
    assert response.data["full_name"] == "Test User"
    assert response.data["skills"] == ["Python", "Django", "SQL"]
    assert response.data["years_of_experience"] == 3

    api.user.profile.refresh_from_db()
    assert api.user.profile.preferred_roles == ["Backend Developer"]


@pytest.mark.django_db
def test_user_can_partially_update_profile(api):
    response = api.patch(
        PROFILE_URL,
        {"full_name": "Updated Name"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["full_name"] == "Updated Name"
    assert response.data["years_of_experience"] == 2


@pytest.mark.django_db
def test_unauthenticated_user_cannot_access_profile():
    client = APIClient()

    response = client.get(PROFILE_URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_invalid_skills_are_rejected(api):
    response = api.patch(
        PROFILE_URL,
        {"skills": ["Python", ""]},
        format="json",
    )

    assert response.status_code == 400
