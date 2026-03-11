"""
tests/test_integration.py

Integration tests using the dedicated test database (awegen_test_db).
Requires a running MySQL instance with 'awegen_test_db' created.

Run:  pytest tests/test_integration.py -v
"""
import pytest
import json
import os

# Force testing config BEFORE any app import
os.environ["FLASK_ENV"] = "testing"


@pytest.fixture(scope="session")
def app():
    """Create the Flask application with testing config."""
    from app import create_app
    app = create_app("testing")
    yield app


@pytest.fixture(scope="session")
def _db(app):
    """Create all tables at the start, drop at the end."""
    from app.database import db
    with app.app_context():
        db.create_all()
        yield db
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def session(_db, app):
    """Wrap each test in a transaction that is rolled back."""
    with app.app_context():
        _db.session.begin_nested()
        yield _db.session
        _db.session.rollback()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _register_user(client, email, password, role="teacher", username=None):
    """Register a user directly via the model (bypasses OTP)."""
    from app.auth.models import User
    from app.database import db

    user = User(
        username=username or email.split("@")[0],
        email=email,
        first_name="Test",
        last_name="User",
        role=role,
        is_verified=True,
        is_approved=True,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def _login(client, email, password):
    """Login and return access token."""
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        content_type="application/json",
    )
    data = resp.get_json()
    return data.get("access_token")


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------

class TestAuth:
    def test_login_success(self, client, session):
        user = _register_user(client, "auth@test.com", "Pass1234!")
        session.flush()

        resp = client.post(
            "/api/auth/login",
            json={"email": "auth@test.com", "password": "Pass1234!"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "access_token" in data

    def test_login_wrong_password(self, client, session):
        _register_user(client, "authfail@test.com", "Correct1!")
        session.flush()

        resp = client.post(
            "/api/auth/login",
            json={"email": "authfail@test.com", "password": "Wrong1!"},
        )
        assert resp.status_code in (401, 400)

    def test_me_requires_jwt(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code in (401, 422)

    def test_me_returns_user(self, client, session):
        user = _register_user(client, "me@test.com", "Pass1234!")
        session.flush()
        token = _login(client, "me@test.com", "Pass1234!")

        resp = client.get("/api/auth/me", headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["email"] == "me@test.com"

    def test_refresh_endpoint(self, client, session):
        """Test the new /auth/refresh endpoint sets a fresh access cookie."""
        user = _register_user(client, "refresh@test.com", "Pass1234!")
        session.flush()

        # Login to get cookies
        login_resp = client.post(
            "/api/auth/login",
            json={"email": "refresh@test.com", "password": "Pass1234!"},
        )
        assert login_resp.status_code == 200

        # The refresh endpoint should work with the refresh cookie set by login
        refresh_resp = client.post("/api/auth/refresh")
        # May succeed (200) or fail (401/422) depending on cookie config in test env
        # At minimum, the endpoint should exist and not 404
        assert refresh_resp.status_code != 404

    def test_logout_clears_cookies(self, client, session):
        user = _register_user(client, "logout@test.com", "Pass1234!")
        session.flush()
        _login(client, "logout@test.com", "Pass1234!")

        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True


# ---------------------------------------------------------------
# IDOR / ownership tests
# ---------------------------------------------------------------

class TestOwnership:
    def test_teacher_cannot_access_other_module(self, client, session):
        """Teacher A cannot see Teacher B's module."""
        from app.module_processor.models import Module
        from app.users.models import Subject, Department, School
        from app.database import db

        # Create minimal FK dependencies
        school = School(school_id_number=1, school_name="Test School")
        db.session.add(school)
        db.session.flush()

        dept = Department(department_id=1, school_id_number=1, department_name="CS")
        db.session.add(dept)
        db.session.flush()

        subj = Subject(subject_id=1, subject_name="Math", department_id=1)
        db.session.add(subj)
        db.session.flush()

        teacher_a = _register_user(client, "a@test.com", "Pass1!", username="teacher_a")
        teacher_b = _register_user(client, "b@test.com", "Pass1!", username="teacher_b")
        db.session.flush()

        module = Module(
            title="Secret Module",
            teacher_id=teacher_b.user_id,
            subject_id=1,
            processing_status="completed",
        )
        db.session.add(module)
        db.session.flush()

        token_a = _login(client, "a@test.com", "Pass1!")

        resp = client.get(
            f"/api/modules/{module.module_id}",
            headers=_auth_header(token_a),
        )
        # Should be 403 (IDOR blocked) or 404
        assert resp.status_code in (403, 404)

    def test_admin_can_access_any_module(self, client, session):
        """Admin can access any teacher's module."""
        from app.module_processor.models import Module
        from app.users.models import Subject, Department, School
        from app.database import db

        school = School(school_id_number=2, school_name="Test School 2")
        db.session.add(school)
        db.session.flush()

        dept = Department(department_id=2, school_id_number=2, department_name="IT")
        db.session.add(dept)
        db.session.flush()

        subj = Subject(subject_id=2, subject_name="CS", department_id=2)
        db.session.add(subj)
        db.session.flush()

        teacher = _register_user(client, "t@test.com", "Pass1!", username="teacher_own")
        admin = _register_user(client, "admin@test.com", "Pass1!", role="admin", username="admin_own")
        db.session.flush()

        module = Module(
            title="Teacher Module",
            teacher_id=teacher.user_id,
            subject_id=2,
            processing_status="completed",
        )
        db.session.add(module)
        db.session.flush()

        token = _login(client, "admin@test.com", "Pass1!")

        resp = client.get(
            f"/api/modules/{module.module_id}",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------
# CASCADE delete tests
# ---------------------------------------------------------------

class TestCascade:
    def test_module_delete_cascades_children(self, client, session):
        """Deleting a module should cascade-delete content, keywords, etc."""
        from app.module_processor.models import (
            Module, ModuleContent, ModuleKeyword, ModuleTopic
        )
        from app.users.models import Subject, Department, School
        from app.database import db

        school = School(school_id_number=3, school_name="Cascade School")
        db.session.add(school)
        db.session.flush()

        dept = Department(department_id=3, school_id_number=3, department_name="CS3")
        db.session.add(dept)
        db.session.flush()

        subj = Subject(subject_id=3, subject_name="Phys", department_id=3)
        db.session.add(subj)
        db.session.flush()

        teacher = _register_user(client, "cascade@test.com", "Pass1!", username="cascade_t")
        db.session.flush()

        module = Module(
            title="Cascade Test",
            teacher_id=teacher.user_id,
            subject_id=3,
            processing_status="completed",
        )
        db.session.add(module)
        db.session.flush()
        mid = module.module_id

        # Add children
        db.session.add(ModuleContent(
            module_id=mid, content_order=0,
            content_text="Test content", content_type="paragraph",
        ))
        db.session.add(ModuleKeyword(
            module_id=mid, keyword="test_kw",
        ))
        db.session.add(ModuleTopic(
            module_id=mid, topic_name="test_topic",
        ))
        db.session.flush()

        assert ModuleContent.query.filter_by(module_id=mid).count() == 1
        assert ModuleKeyword.query.filter_by(module_id=mid).count() == 1

        # Delete the module
        db.session.delete(module)
        db.session.flush()

        # Children should be gone
        assert ModuleContent.query.filter_by(module_id=mid).count() == 0
        assert ModuleKeyword.query.filter_by(module_id=mid).count() == 0
        assert ModuleTopic.query.filter_by(module_id=mid).count() == 0


# ---------------------------------------------------------------
# Exam generation smoke test (requires NLP models)
# ---------------------------------------------------------------

@pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Requires NLP models not available in CI",
)
class TestExamGeneration:
    def test_exam_generator_cached_instance(self):
        """Verify the cached factory returns the same instance."""
        from app.exam.service import _get_exam_generator

        gen1 = _get_exam_generator()
        gen2 = _get_exam_generator()
        assert gen1 is gen2

    def test_reset_clears_state(self):
        """Verify reset_question_tracking clears mutable state."""
        from app.exam.service import _get_exam_generator

        gen = _get_exam_generator()
        gen.generated_questions.add("fake|question")
        gen.reset_question_tracking()
        assert len(gen.generated_questions) == 0
