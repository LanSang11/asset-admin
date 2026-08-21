FROM node:18.20.4-alpine3.20 AS web

WORKDIR /opt/asset-management-system
COPY /web ./web
# package-lock.json 已通过 overrides 固定 ESM 兼容的传递依赖版本，npm ci 可复现构建
RUN cd /opt/asset-management-system/web && npm ci --registry=https://registry.npmmirror.com && npm run build


FROM python:3.11-slim-bullseye

WORKDIR /opt/asset-management-system
ADD . .
COPY /deploy/entrypoint.sh .

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked,id=core-apt \
    --mount=type=cache,target=/var/lib/apt,sharing=locked,id=core-apt \
    sed -i "s@http://deb.debian.org@http://mirrors.tuna.tsinghua.edu.cn@g" /etc/apt/sources.list \
    && sed -i "s@http://security.debian.org@http://mirrors.tuna.tsinghua.edu.cn@g" /etc/apt/sources.list \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev bash nginx vim curl procps net-tools

RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY --from=web /opt/asset-management-system/web/dist /opt/asset-management-system/web/dist
ADD /deploy/web.conf /etc/nginx/sites-available/web.conf
RUN rm -f /etc/nginx/sites-enabled/default \ 
    && ln -s /etc/nginx/sites-available/web.conf /etc/nginx/sites-enabled/ 

ENV LANG=zh_CN.UTF-8
EXPOSE 80

ENTRYPOINT [ "sh", "entrypoint.sh" ]