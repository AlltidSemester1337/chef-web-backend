# Chef Web backend

Web version of [app](https://github.com/AlltidSemester1337/chef) built using reflex.dev, deployed as backend only on cloud run (frontend hosted statically on WP web server).

Try it live at [demo](https://humlekotte.nu/chef-web/)!

A personal cooking assistant app (Reflex.dev) to suggest recipes for cooking. Built on vertexai chat and
firebase. Requires integration towards
vertexai using google-services.json credentials for SA in order to run.
Also requires a firebaseDbUrl to be set in <TODO> when building the app to run using
ChatHistoryRealtimeDatabasePersistence.

Run the app (backend) locally using reflex run --backend-only --backend-port 8080 or refer to Dockerfile and Reflex docs.

Features:

- 1.0.x - Initial release, dummy chat
- 1.1.x - Implement all features from app snapshot (latest version) (see [app](https://github.com/AlltidSemester1337/chef))
- After this versions will be bumped to match app as features are released.

## Demo 1.0 release

[Demo 1.0](https://humlekotte.nu/chef-web/)

## Deployment

### In future version (?) or non-mac (Docker for Mac?) / better GCP support could perhaps be hosted fully on cloud run instead of backend only

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

Upload to WP web server in public-html/chef-web, profit!

## How to make contributions?

Fork or reach out to authors humlekottekonsult@gmail.com

## Support, feature request, question etc
This project is owned and currently operated and maintained by [Humlekotte Konsultbolag](https://www.humlekotte.nu). Any questions reach out via email humlekottekonsult@gmail.com
