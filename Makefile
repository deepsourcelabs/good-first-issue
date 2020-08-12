THEME_PATH = 'themes/lucy/'

pre-build:
	curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python && \
	source $HOME/.poetry/env && \
	poetry self update --preview && \
	poetry install --no-dev

build:
	cd $(THEME_PATH) && \
	npm install && \
	cd ../.. && \
	npm install -g postcss-cli autoprefixer && \
	hugo

generate:
	poetry run python gfi/populate.py

tweet:
	poetry run python gfi/tweet.py

index:
	poetry run python gfi/index.py

generate-prod:
	make pre-build
	make generate
	make tweet
	make build

test:
	poetry run python gfi/test_data.py

.DEFAULT_GOAL := build
