from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import bcrypt

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='auditor')  # admin, auditor
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    verifications = db.relationship('AuditVerification', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set password."""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        """Check if provided password matches hash."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def is_admin(self):
        """Check if user has admin role."""
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.username}>'

class GDPRChecklist(db.Model):
    """GDPR checklist questions."""
    __tablename__ = 'gdpr_checklist'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.String(10), unique=True, nullable=False, index=True)
    category = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(100), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    gdpr_reference = db.Column(db.String(100), nullable=False)
    
    # Relationships
    question_answers = db.relationship('QuestionAnswer', backref='checklist', lazy='dynamic')
    
    def __repr__(self):
        return f'<GDPRChecklist {self.question_id}>'

class Domain(db.Model):
    """Domain with AI analysis results."""
    __tablename__ = 'domains'
    
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True, nullable=False, index=True)
    
    # AI results (read-only)
    compliance_label = db.Column(db.String(50))  # COMPLIANT, PARTIALLY_COMPLIANT, NON_COMPLIANT
    compliance_score = db.Column(db.Integer)
    language_detected = db.Column(db.String(50))
    summary = db.Column(db.Text)
    translation_performed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50))  # success, error, etc.
    error = db.Column(db.Text)
    
    # Privacy policy info
    privacy_url = db.Column(db.Text)
    privacy_source = db.Column(db.String(100))
    privacy_file_path = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    question_answers = db.relationship('QuestionAnswer', backref='domain', lazy='dynamic', cascade='all, delete-orphan')
    verifications = db.relationship('AuditVerification', backref='domain', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_privacy_text(self):
        """Read and return privacy policy text from file."""
        if self.privacy_file_path:
            try:
                with open(self.privacy_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                return None
        return None
    
    def __repr__(self):
        return f'<Domain {self.domain}>'

class QuestionAnswer(db.Model):
    """AI answers for GDPR checklist questions."""
    __tablename__ = 'question_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id'), nullable=False, index=True)
    question_id = db.Column(db.String(10), db.ForeignKey('gdpr_checklist.question_id'), nullable=False, index=True)
    
    # AI results (read-only)
    ai_answer = db.Column(db.String(20))  # YES, NO, PARTIAL
    ai_evidence = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    verifications = db.relationship('AuditVerification', backref='question_answer', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<QuestionAnswer {self.domain_id}-{self.question_id}>'

class AuditVerification(db.Model):
    """User verifications of AI results."""
    __tablename__ = 'audit_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    question_answer_id = db.Column(db.Integer, db.ForeignKey('question_answers.id'), nullable=True, index=True)
    
    verification_status = db.Column(db.String(20), nullable=False)  # correct, incorrect, needs_review
    user_comment = db.Column(db.Text)
    review_complete = db.Column(db.Boolean, default=False, nullable=False)  # Track if user completed full review
    
    verified_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<AuditVerification {self.domain_id}-{self.user_id}>'
