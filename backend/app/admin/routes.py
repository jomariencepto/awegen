from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.admin.service import AdminService
from app.utils.decorators import role_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def get_dashboard():
    result, status_code = AdminService.get_dashboard_stats()
    return jsonify(result), status_code


@admin_bp.route('/users/all', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def get_all_users():
    """Get all users for Admin Dashboard"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    result, status_code = AdminService.get_all_users(page, per_page)
    return jsonify(result), status_code


@admin_bp.route('/logs', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def get_system_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    result, status_code = AdminService.get_system_logs(page, per_page)
    return jsonify(result), status_code


@admin_bp.route('/settings', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def get_system_settings():
    result, status_code = AdminService.get_system_settings()
    return jsonify(result), status_code


@admin_bp.route('/settings', methods=['PUT'])
@jwt_required()
@role_required(['admin'])
def update_system_settings():
    data = request.get_json()
    result, status_code = AdminService.update_system_settings(data)
    return jsonify(result), status_code


@admin_bp.route('/exam-password', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def get_exam_password_settings():
    result, status_code = AdminService.get_exam_password_settings()
    return jsonify(result), status_code


@admin_bp.route('/exam-password', methods=['PUT'])
@jwt_required()
@role_required(['admin'])
def update_exam_password_settings():
    data = request.get_json() or {}
    result, status_code = AdminService.update_exam_password(data)
    return jsonify(result), status_code


@admin_bp.route('/reports', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def get_system_reports():
    result, status_code = AdminService.get_system_reports()
    return jsonify(result), status_code


@admin_bp.route('/departments-subjects', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def get_departments_subjects():
    """Get all departments with nested subjects for admin management."""
    result, status_code = AdminService.get_departments_with_subjects()
    return jsonify(result), status_code


@admin_bp.route('/departments', methods=['POST'])
@jwt_required()
@role_required(['admin'])
def create_department():
    data = request.get_json() or {}
    result, status_code = AdminService.create_department(data)
    return jsonify(result), status_code


@admin_bp.route('/subjects', methods=['POST'])
@jwt_required()
@role_required(['admin'])
def create_subject():
    data = request.get_json() or {}
    result, status_code = AdminService.create_subject(data)
    return jsonify(result), status_code


@admin_bp.route('/subjects/<int:subject_id>', methods=['PUT'])
@jwt_required()
@role_required(['admin'])
def update_subject(subject_id):
    data = request.get_json() or {}
    result, status_code = AdminService.update_subject(subject_id, data)
    return jsonify(result), status_code


@admin_bp.route('/subjects/<int:subject_id>', methods=['DELETE'])
@jwt_required()
@role_required(['admin'])
def delete_subject(subject_id):
    result, status_code = AdminService.delete_subject(subject_id)
    return jsonify(result), status_code
