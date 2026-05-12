PREFIX  ?= $(HOME)/.local
BINDIR   = $(PREFIX)/bin
DATADIR  = $(PREFIX)/share
ICONDIR  = $(DATADIR)/icons/hicolor/scalable/apps
APPDIR   = $(DATADIR)/applications
AUTODIR  = $(HOME)/.config/autostart
HNDATA   = $(DATADIR)/hotnote
LIBDIR   = $(DATADIR)/hotnote/lib

.PHONY: install uninstall test

install:
	@echo "Installing HotNote to $(PREFIX) …"
	install -Dm755 bin/hotnote           $(BINDIR)/hotnote
	install -Dm755 bin/hotnote-indicator $(BINDIR)/hotnote-indicator
	install -Dm644 lib/hotnotelib.py     $(LIBDIR)/hotnotelib.py
	install -Dm644 data/icons/hotnote.svg      $(ICONDIR)/hotnote.svg
	install -Dm644 data/icons/hotnote-tray.svg $(HNDATA)/icon.svg
	mkdir -p $(APPDIR) $(AUTODIR)
	sed 's|@PREFIX@|$(PREFIX)|g' data/hotnote.desktop.in           > $(APPDIR)/hotnote.desktop
	sed 's|@PREFIX@|$(PREFIX)|g' data/hotnote-indicator.desktop.in > $(AUTODIR)/hotnote-indicator.desktop
	mkdir -p $(HNDATA)
	@if command -v gtk-update-icon-cache >/dev/null 2>&1; then \
		gtk-update-icon-cache -f -t $(DATADIR)/icons/hicolor 2>/dev/null || true; \
	fi
	@echo "Done. Run 'hotnote-indicator' or log out/in for autostart."

uninstall:
	@echo "Removing HotNote from $(PREFIX) …"
	rm -f $(BINDIR)/hotnote
	rm -f $(BINDIR)/hotnote-indicator
	rm -f $(LIBDIR)/hotnotelib.py
	rmdir $(LIBDIR) 2>/dev/null || true
	rm -f $(ICONDIR)/hotnote.svg
	rm -f $(HNDATA)/icon.svg
	rm -f $(APPDIR)/hotnote.desktop
	rm -f $(AUTODIR)/hotnote-indicator.desktop
	@if command -v gtk-update-icon-cache >/dev/null 2>&1; then \
		gtk-update-icon-cache -f -t $(DATADIR)/icons/hicolor 2>/dev/null || true; \
	fi
	@echo "Done."

test:
	pip3 install -r requirements.txt
	python3 -m pytest tests/ -v
