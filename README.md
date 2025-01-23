## TODO: Fill description, look at app

## Deployment

# In future version (?) or non-mac (Docker for Mac?) / better GCP support could perhaps be hosted fully on cloud run except only backend

# BACKEND:

TAG=gcr.io/idyllic-bloom-425307-r6/chef-web-backend:<NEXT_VERSION>

docker buildx build --platform linux/amd64 -t $TAG .

docker push $TAG

gcloud run deploy chef-web-backend --image $TAG --platform managed --memory 2Gi --region europe-north1
--allow-unauthenticated

# FRONTEND:

(grab service url)

API_URL=<SERVICE_URL> reflex export --frontend-only

Upload zip, extract

Manually download, update index.html to replace relative paths with prefix /chef-web for all static files (WHY???)

Upload, profit!