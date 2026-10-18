
set -o errexit

pip install -r requirements.txt

npm --prefix frontend ci --no-fund
npm --prefix frontend run build

flask db upgrade

python create_admin.py
