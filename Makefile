TODAY := $(shell date +%Y-%m-%d)
EMAILS_DIR := ./emails

all: personal work

emails-dir:
	mkdir -p $(EMAILS_DIR)

personal: emails-dir
	@if [ -e $(EMAILS_DIR)/$(TODAY)_1_personal.md ]; then \
		./process_emails.py personal --partial; \
	else \
		./process_emails.py personal; \
	fi

work: emails-dir
	@if [ -e $(EMAILS_DIR)/$(TODAY)_1_work.md ]; then \
		./process_emails.py work --partial; \
	else \
		./process_emails.py work; \
	fi

display: personal work
	glow $(EMAILS_DIR)/$(TODAY)_1_work.md
	glow $(EMAILS_DIR)/$(TODAY)_1_personal.md

display-partial: personal work
	glow $(EMAILS_DIR)/$(TODAY)_1_work_partial.md
	glow $(EMAILS_DIR)/$(TODAY)_1_personal.md
