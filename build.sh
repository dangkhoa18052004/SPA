
set -o errexit

pip install -r requirements.txt

flask db upgrade

python -c "from app import create_app, db; from app.models import User; app = create_app(); app.app_context().push(); admin = User.query.filter_by(username='admin').first(); 
if not admin: 
    admin = User(username='admin', email='admin@binspa.com', role='admin'); 
    admin.set_password('Admin@123'); 
    db.session.add(admin); 
    db.session.commit(); 
    print('Admin created')"