# shs

Technologies:
   python3
   MySql
   Gcp Setup 

export GOOGLE_APPLICATION_CREDENTIALS="/home/ganesh/projects/smarthospitalsystem/shs.json"
test Google Creadentials:
	python manage.py shell
	from google.auth import default
	credentials, project_id = default()
	print("Project ID:", project_id)
	print("Credentials type:", type(credentials))
production:
	pip3 install google-auth
	pip3 install uvicorn
	uvicorn smarthospitalsystem.asgi:application --host 0.0.0.0 --port 8000
	pip3 install gunicorn
	gunicorn smarthospitalsystem.wsgi:application
development:
	python3 manage.py runserver	
admin user creation:
	python3 manage.py createsuperuser
	
For Google Cloud Storage (with django-storages):
DEFAULT_FILE_STORAGE = "storages.backends.gcloud.GoogleCloudStorage"
GS_BUCKET_NAME = "your-bucket-name"
GS_CREDENTIALS = GS_CREDENTIALS

---------------------------------------------------------------------------------

Which scope should you use?

General purpose (all GCP APIs):
"https://www.googleapis.com/auth/cloud-platform"

Cloud Storage only:
"https://www.googleapis.com/auth/devstorage.read_write"

BigQuery only:
"https://www.googleapis.com/auth/bigquery"

strat project of django:
	django-admin startproject shs
	
pip install django-extensions
pip install djangorestframework
