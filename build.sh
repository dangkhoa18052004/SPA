
set -o errexit

pip install -r requirements.txt

flask db upgrade

python create_admin.py