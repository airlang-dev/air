REGION ?= us-east-1
ACCOUNT_ID ?= $(shell aws sts get-caller-identity --query Account --output text)

FUNCTIONS = air_sdk_gate air_sdk_aggregate air_sdk_verify air_sdk_decide air_sdk_session

.PHONY: all package deploy clean $(FUNCTIONS)

all: package

# ── Package ────────────────────────────────────────────────────────────────────

package: $(addprefix dist/, $(addsuffix .zip, $(FUNCTIONS)))

dist/%.zip: %/handler.py %/requirements.txt
	@mkdir -p dist
	@echo "Packaging $*..."
	@rm -rf /tmp/pkg_$*
	@mkdir -p /tmp/pkg_$*
	@pip install -r $*/requirements.txt -t /tmp/pkg_$* -q
	@cp $*/handler.py /tmp/pkg_$*/
	@cd /tmp/pkg_$* && zip -r $(CURDIR)/dist/$*.zip . -q
	@echo "  → dist/$*.zip"

# ── Deploy ─────────────────────────────────────────────────────────────────────

deploy: package
	@for fn in $(FUNCTIONS); do \
		fname=$$(echo $$fn | tr '_' '-'); \
		echo "Deploying $$fname to $(REGION)..."; \
		if aws lambda get-function --function-name $$fname --region $(REGION) > /dev/null 2>&1; then \
			aws lambda update-function-code \
				--function-name $$fname \
				--zip-file fileb://dist/$${fn}.zip \
				--region $(REGION) > /dev/null; \
			echo "  → updated $$fname"; \
		else \
			aws lambda create-function \
				--function-name $$fname \
				--runtime python3.12 \
				--role arn:aws:iam::$(ACCOUNT_ID):role/air-sdk-lambda-role \
				--handler handler.lambda_handler \
				--zip-file fileb://dist/$${fn}.zip \
				--region $(REGION) > /dev/null; \
			echo "  → created $$fname"; \
		fi; \
	done

# ── Clean ──────────────────────────────────────────────────────────────────────

clean:
	rm -rf dist/ /tmp/pkg_air_sdk_*
