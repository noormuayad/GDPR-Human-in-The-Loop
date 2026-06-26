# GDPR Audit Website

A Flask-based web application for auditing AI-generated GDPR compliance results for EU websites.

## Features

- **Dashboard**: View statistics and browse all analyzed domains
- **Domain Review**: Detailed view of AI analysis with privacy policy text
- **Audit Interface**: Verify AI results by marking questions as correct/incorrect
- **User Management**: Admin panel for creating and managing users
- **Non-destructive Auditing**: Original AI results are never modified
- **Verification Tracking**: Track which user verified each result

## Setup Instructions

### Prerequisites

- Python 3.8+
- PostgreSQL (for production) or SQLite (for development)

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Initialize the database and import data:**
   ```bash
   python import_data.py
   ```
   This will:
   - Create database tables
   - Import GDPR checklist from `gdpr_checklist.json`
   - Import compliance results from `compliance_results.csv`
   - Import privacy URLs from `privacy_results.csv`
   - Create initial admin user (username: `admin`, password: `admin123`)

4. **Run the application:**
   ```bash
   python run.py
   ```

5. **Access the application:**
   - Open browser to `http://localhost:5000`
   - Login with admin user (username: `admin`, password: `admin123`)
   - **IMPORTANT**: Change the default admin password immediately!

## Default Credentials

- **Username**: admin
- **Password**: admin123

**Change this password immediately after first login!**

## Project Structure

```
website/
├── app.py                 # Flask application factory
├── config.py              # Configuration settings
├── models.py              # SQLAlchemy database models
├── import_data.py         # Data import script
├── run.py                 # Application entry point
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── gdpr_checklist.json   # GDPR checklist questions
├── compliance_results.csv # AI compliance analysis results
├── privacy_results.csv    # Privacy policy URLs
├── privacy/               # Privacy policy text files
├── templates/
│   ├── base.html         # Base template
│   ├── login.html        # Login page
│   ├── dashboard.html    # Dashboard
│   ├── domain_detail.html # Domain review page
│   ├── my_reviews.html   # Review history
│   └── admin/
│       ├── base.html     # Admin base template
│       └── users.html    # User management
├── instance/             # Instance folder for SQLite database
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose configuration
└── render.yaml           # Render deployment configuration
```

## Database Schema

- **Users**: User accounts with roles (admin, auditor)
- **GDPRChecklist**: 25 GDPR checklist questions
- **Domains**: AI analysis results for each domain
- **QuestionAnswer**: AI answers for each checklist question
- **AuditVerification**: User verifications of AI results

## Usage

### For Auditors

1. Login to the application
2. Browse domains on the dashboard
3. Click "Review" on a domain to see detailed analysis
4. Compare AI results with the actual privacy policy text
5. Mark each question as correct/incorrect/needs review
6. Add comments explaining your verification
7. Click the link to view the original privacy policy for confirmation

### For Admins

1. Access the Admin panel from the navigation
2. Create new auditor accounts
3. Reset user passwords
4. Deactivate inactive users
5. View system statistics

## Security Notes

- Change the default admin password immediately
- Use strong passwords for all users
- Use PostgreSQL in production (not SQLite)
- Set a strong SECRET_KEY in production
- Enable HTTPS in production
- Regularly backup the database

## Development

### Running in Development Mode

```bash
export FLASK_ENV=development
python run.py
```

### Running in Production Mode

```bash
export FLASK_ENV=production
# Use a production WSGI server like gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

## Troubleshooting

### Import Script Issues

If the import script fails:
- Ensure the data files exist in the website directory: `compliance_results.csv`, `privacy_results.csv`, and `gdpr_checklist.json`
- Check that the `privacy/` directory exists
- Verify the privacy directory path in `config.py`

### Database Connection Issues

For PostgreSQL:
- Ensure PostgreSQL is running
- Verify the DATABASE_URL in `.env` is correct
- Check that the database exists

For SQLite:
- Ensure the application has write permissions to the directory
- Check that the `instance` directory exists

## License

This project is part of the GDPR compliance analysis project.
