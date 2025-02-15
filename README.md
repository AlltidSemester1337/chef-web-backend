# Chef Web backend

Web version of [app](https://github.com/AlltidSemester1337/chef) built using reflex.dev, deployed as backend only on
cloud run (frontend hosted statically on WP web server).

Try it live at [demo](https://humlekotte.nu/chef-web/recipes)!
Access token for closed beta testing can be requested by contacting author, see "Support, feature request, question etc"
section at the bottom.

A personal cooking assistant app (Reflex.dev) to suggest recipes for cooking. Built on vertexai chat and
firebase. Requires integration towards vertexai using SA in order to run.
Also requires a firebaseDbUrl to be set in $FIREBASE_URL and $ACCESS_TOKEN when building the app to run.

Run the app (backend) locally using reflex run --backend-only --backend-port 8080 or refer to Dockerfile and Reflex
docs. A SA with access to firebase / realtimedb is required to run.

Features:

- 1.0.5 - Migrated features from app to web version
- 1.6.0 - Added Collections feature
Refer to [app](https://github.com/AlltidSemester1337/chef) for future versions plan.

## Demo v1.0.5 release

[Demo v1.0.5](https://humlekotte.nu/chef-web/)
Access token for closed beta testing can be requested by contacting author, see "Support, feature request, question etc"
section at the bottom.

## Deployment

### In future version (?) or non-mac (Docker for Mac?) / better GCP support could perhaps be hosted fully on cloud run instead of backend only

# BACKEND:

TAG=gcr.io/idyllic-bloom-425307-r6/chef-web-backend:<NEXT_VERSION>

docker buildx build --platform linux/amd64 -t $TAG .

docker push $TAG

gcloud run deploy chef-web-backend --image $TAG --platform managed --memory 2Gi --region europe-north1 \
--allow-unauthenticated --update-env-vars ACCESS_TOKEN=$ACCESS_TOKEN,FIREBASE_URL=$FIREBASE_URL \
--service-account $SERVICE_ACCOUNT

# FRONTEND:

SERVICE_URL=<grab backend service url>

API_URL=$SERVICE_URL reflex export --frontend-only

Upload zip, extract

Manually download, update index.html to replace relative paths with prefix /chef-web for all static files (WHY???)

Upload to WP web server in public-html/chef-web, profit!

## How to make contributions?

Fork or reach out to authors humlekottekonsult@gmail.com

## Support, feature request, question etc

This project is owned and currently operated and maintained by [Humlekotte Konsultbolag](https://www.humlekotte.nu). Any
questions or request access token for closed beta reach out via
email [humlekottekonsult@gmail.com](mailto:humlekottekonsult@gmail.com)
