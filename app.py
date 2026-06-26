"""
Flask application factory for GDPR Audit Website.
"""

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
import os

from config import config
from models import db, User, Domain, GDPRChecklist, QuestionAnswer, AuditVerification

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))

def admin_required(f):
    """Decorator to require admin role for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def create_app(config_name='default'):
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Register blueprints (if any)
    # from .auth import auth_bp
    # app.register_blueprint(auth_bp)
    
    # Register routes
    register_routes(app)
    
    return app

def register_routes(app):
    """Register all application routes."""
    
    @app.route('/')
    def index():
        """Redirect to dashboard or login."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """User login page."""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password) and user.is_active:
                login_user(user)
                user.last_login = db.func.current_timestamp()
                db.session.commit()
                
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        """User logout."""
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        """Main dashboard with statistics and domain list."""
        # Get statistics
        total_domains = Domain.query.count()
        total_verified = AuditVerification.query.count()
        my_verified = AuditVerification.query.filter_by(user_id=current_user.id).count()
        my_completed = AuditVerification.query.filter_by(user_id=current_user.id, review_complete=True).count()
        
        # Compliance distribution
        compliant_count = Domain.query.filter_by(compliance_label='COMPLIANT').count()
        partial_count = Domain.query.filter_by(compliance_label='PARTIALLY_COMPLIANT').count()
        non_compliant_count = Domain.query.filter_by(compliance_label='NON_COMPLIANT').count()
        
        # Get filters
        search = request.args.get('search', '')
        compliance_filter = request.args.get('compliance', '')
        audit_filter = request.args.get('audit', 'not_audited_by_anyone')  # default: unaudited by anyone
        language_filter = request.args.get('language', '')
        page = request.args.get('page', 1, type=int)
        
        # Build query
        query = Domain.query
        
        if search:
            query = query.filter(Domain.domain.ilike(f'%{search}%'))
        
        if compliance_filter:
            query = query.filter_by(compliance_label=compliance_filter)
        
        if language_filter:
            query = query.filter_by(language_detected=language_filter)
        
        # Filter by audit status
        if audit_filter == 'not_audited':
            # Get domains that current user has not audited
            audited_domain_ids = db.session.query(AuditVerification.domain_id).filter(
                AuditVerification.user_id == current_user.id
            ).distinct().all()
            audited_ids = [d[0] for d in audited_domain_ids]
            if audited_ids:
                query = query.filter(~Domain.id.in_(audited_ids))
        elif audit_filter == 'not_audited_by_anyone':
            # Get domains that NO user has audited yet
            any_audited_ids = db.session.query(AuditVerification.domain_id).distinct().all()
            any_audited_ids = [d[0] for d in any_audited_ids]
            if any_audited_ids:
                query = query.filter(~Domain.id.in_(any_audited_ids))
        
        # Paginate
        per_page = app.config['DOMAINS_PER_PAGE']
        pagination = query.order_by(Domain.domain).paginate(
            page=page, per_page=per_page, error_out=False
        )
        domains = pagination.items
        
        stats = {
            'total_domains': total_domains,
            'total_verified': total_verified,
            'my_verified': my_verified,
            'my_completed': my_completed,
            'compliant': compliant_count,
            'partial': partial_count,
            'non_compliant': non_compliant_count
        }
        
        # Get distinct languages for filter dropdown (exclude nulls/empty)
        available_languages = db.session.query(Domain.language_detected)\
            .filter(Domain.language_detected.isnot(None))\
            .filter(Domain.language_detected != '')\
            .distinct()\
            .order_by(Domain.language_detected)\
            .all()
        available_languages = [row[0] for row in available_languages]

        return render_template(
            'dashboard.html',
            domains=domains,
            pagination=pagination,
            stats=stats,
            search=search,
            compliance_filter=compliance_filter,
            audit_filter=audit_filter,
            language_filter=language_filter,
            available_languages=available_languages
        )
    
    @app.route('/my-reviews')
    @login_required
    def my_reviews():
        """Show all review history from all users."""
        page = request.args.get('page', 1, type=int)
        
        # Get all domains that have been audited by any user
        audited_verifications = db.session.query(
            AuditVerification.domain_id
        ).filter(
            AuditVerification.question_answer_id.is_(None)  # Overall verifications only
        ).distinct().all()
        
        audited_domain_ids = [v[0] for v in audited_verifications]
        
        if not audited_domain_ids:
            return render_template('my_reviews.html', domains=[], pagination=None)
        
        # Get domains with pagination
        per_page = app.config['DOMAINS_PER_PAGE']
        pagination = Domain.query.filter(
            Domain.id.in_(audited_domain_ids)
        ).order_by(Domain.domain).paginate(
            page=page, per_page=per_page, error_out=False
        )
        domains = pagination.items
        
        # Get all verifications for each domain
        verification_map = {}
        for domain in domains:
            verifications = AuditVerification.query.filter_by(
                domain_id=domain.id,
                question_answer_id=None
            ).all()
            verification_map[domain.id] = verifications
        
        return render_template(
            'my_reviews.html',
            domains=domains,
            pagination=pagination,
            verification_map=verification_map
        )
    
    @app.route('/domain/<int:domain_id>')
    @login_required
    def domain_detail(domain_id):
        """Domain detail view with audit interface."""
        domain = Domain.query.get_or_404(domain_id)
        
        # Get all question answers with checklist info
        question_answers = db.session.query(
            QuestionAnswer, GDPRChecklist
        ).join(
            GDPRChecklist, QuestionAnswer.question_id == GDPRChecklist.question_id
        ).filter(
            QuestionAnswer.domain_id == domain_id
        ).order_by(GDPRChecklist.question_id).all()
        
        # Get existing verifications
        verifications = AuditVerification.query.filter_by(domain_id=domain_id).all()
        verification_map = {}
        for v in verifications:
            key = v.question_answer_id if v.question_answer_id else 'overall'
            verification_map[key] = v
        
        return render_template(
            'domain_detail.html',
            domain=domain,
            question_answers=question_answers,
            verification_map=verification_map
        )
    
    @app.route('/api/verify', methods=['POST'])
    @login_required
    def verify():
        """Submit verification via AJAX."""
        data = request.get_json()
        
        domain_id = data.get('domain_id')
        question_answer_id = data.get('question_answer_id')  # null for overall label
        verification_status = data.get('status')  # correct, incorrect, needs_review
        user_comment = data.get('comment', '')
        
        # Create or update verification
        if question_answer_id:
            # Verify specific question
            verification = AuditVerification.query.filter_by(
                domain_id=domain_id,
                question_answer_id=question_answer_id,
                user_id=current_user.id
            ).first()
            
            if verification:
                verification.verification_status = verification_status
                verification.user_comment = user_comment
                verification.verified_at = db.func.current_timestamp()
            else:
                verification = AuditVerification(
                    domain_id=domain_id,
                    question_answer_id=question_answer_id,
                    user_id=current_user.id,
                    verification_status=verification_status,
                    user_comment=user_comment
                )
                db.session.add(verification)
        else:
            # Verify overall label
            verification = AuditVerification.query.filter_by(
                domain_id=domain_id,
                question_answer_id=None,
                user_id=current_user.id
            ).first()
            
            if verification:
                verification.verification_status = verification_status
                verification.user_comment = user_comment
                verification.verified_at = db.func.current_timestamp()
            else:
                verification = AuditVerification(
                    domain_id=domain_id,
                    question_answer_id=None,
                    user_id=current_user.id,
                    verification_status=verification_status,
                    user_comment=user_comment
                )
                db.session.add(verification)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Verification saved'})
    
    @app.route('/api/bulk-verify', methods=['POST'])
    @login_required
    def bulk_verify():
        """Submit multiple verifications via AJAX."""
        data = request.get_json()
        
        domain_id = data.get('domain_id')
        verifications = data.get('verifications', [])
        
        if not verifications:
            return jsonify({'success': False, 'message': 'No verifications provided'})
        
        try:
            for verification_data in verifications:
                question_answer_id = verification_data.get('question_answer_id')
                verification_status = verification_data.get('status')
                user_comment = verification_data.get('comment', '')
                
                # Create or update verification
                verification = AuditVerification.query.filter_by(
                    domain_id=domain_id,
                    question_answer_id=question_answer_id,
                    user_id=current_user.id
                ).first()
                
                if verification:
                    verification.verification_status = verification_status
                    verification.user_comment = user_comment
                    verification.verified_at = db.func.current_timestamp()
                else:
                    verification = AuditVerification(
                        domain_id=domain_id,
                        question_answer_id=question_answer_id,
                        user_id=current_user.id,
                        verification_status=verification_status,
                        user_comment=user_comment
                    )
                    db.session.add(verification)
            
            db.session.commit()
            return jsonify({'success': True, 'message': f'{len(verifications)} verifications saved'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/mark-complete', methods=['POST'])
    @login_required
    def mark_complete():
        """Mark domain review as complete for current user."""
        data = request.get_json()
        domain_id = data.get('domain_id')
        
        # Get the overall verification for this domain and user
        verification = AuditVerification.query.filter_by(
            domain_id=domain_id,
            question_answer_id=None,
            user_id=current_user.id
        ).first()
        
        if verification:
            verification.review_complete = True
        else:
            # Create verification if it doesn't exist
            verification = AuditVerification(
                domain_id=domain_id,
                question_answer_id=None,
                user_id=current_user.id,
                verification_status='needs_review',
                review_complete=True
            )
            db.session.add(verification)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Review marked as complete'})
    
    @app.route('/api/delete-verifications', methods=['POST'])
    @login_required
    def delete_verifications():
        """Delete verifications for selected domains."""
        data = request.get_json()
        domain_ids = data.get('domain_ids', [])
        
        if not domain_ids:
            return jsonify({'success': False, 'message': 'No domain IDs provided'})
        
        try:
            # Delete all verifications for the selected domains by the current user
            deleted_count = AuditVerification.query.filter(
                AuditVerification.domain_id.in_(domain_ids),
                AuditVerification.user_id == current_user.id
            ).delete(synchronize_session=False)
            
            db.session.commit()
            
            return jsonify({'success': True, 'message': f'{deleted_count} verification(s) deleted'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/statistics')
    @login_required
    def statistics():
        """Get dashboard statistics via AJAX."""
        total_domains = Domain.query.count()
        total_verified = AuditVerification.query.count()
        
        compliant_count = Domain.query.filter_by(compliance_label='COMPLIANT').count()
        partial_count = Domain.query.filter_by(compliance_label='PARTIALLY_COMPLIANT').count()
        non_compliant_count = Domain.query.filter_by(compliance_label='NON_COMPLIANT').count()
        
        return jsonify({
            'total_domains': total_domains,
            'total_verified': total_verified,
            'compliant': compliant_count,
            'partial': partial_count,
            'non_compliant': non_compliant_count
        })
    
    # Admin routes
    @app.route('/admin')
    @login_required
    @admin_required
    def admin_dashboard():
        """Admin dashboard."""
        users = User.query.all()
        total_users = User.query.count()
        total_verifications = AuditVerification.query.count()
        
        return render_template(
            'admin/users.html',
            users=users,
            total_users=total_users,
            total_verifications=total_verifications
        )
    
    @app.route('/admin/users/create', methods=['POST'])
    @login_required
    @admin_required
    def create_user():
        """Create new user (admin only)."""
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'auditor')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        user = User(username=username, role=role, is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {username} created successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
    
    @app.route('/admin/users/<int:user_id>/deactivate', methods=['POST'])
    @login_required
    @admin_required
    def deactivate_user(user_id):
        """Deactivate user (admin only)."""
        user = User.query.get_or_404(user_id)
        
        if user.username == 'admin':
            flash('Cannot deactivate admin user.', 'danger')
            return redirect(url_for('admin_dashboard'))
        
        user.is_active = False
        db.session.commit()
        
        flash(f'User {user.username} deactivated.', 'success')
        return redirect(url_for('admin_dashboard'))
    
    @app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
    @login_required
    @admin_required
    def reset_password(user_id):
        """Reset user password (admin only)."""
        user = User.query.get_or_404(user_id)
        new_password = request.form.get('new_password')
        
        user.set_password(new_password)
        db.session.commit()
        
        flash(f'Password reset for {user.username}.', 'success')
        return redirect(url_for('admin_dashboard'))
