class Orbitra < Formula
  include Language::Python::Virtualenv

  desc "Self-hosted deterministic web intelligence engine — no AI, no API keys"
  homepage "https://github.com/emmi-dev12/Orbitra"
  url "https://github.com/emmi-dev12/Orbitra/archive/refs/heads/main.tar.gz"
  version "1.0.0"
  license "MIT"

  depends_on "python@3.12"

  resource "playwright" do
    url "https://files.pythonhosted.org/packages/source/p/playwright/playwright-1.40.0.tar.gz"
    # sha256 filled in on first `brew audit` or `brew fetch`
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/source/h/httpx/httpx-0.25.2.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.7.0.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "uvicorn" do
    url "https://files.pythonhosted.org/packages/source/u/uvicorn/uvicorn-0.24.0.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "fastapi" do
    url "https://files.pythonhosted.org/packages/source/f/fastapi/fastapi-0.104.1.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "aiosqlite" do
    url "https://files.pythonhosted.org/packages/source/a/aiosqlite/aiosqlite-0.19.0.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  def install
    virtualenv_install_with_resources

    # Install Playwright browser binaries
    system libexec/"bin/python", "-m", "playwright", "install", "chromium"

    # Shim script
    (bin/"orbitra").write <<~SH
      #!/bin/sh
      exec "#{libexec}/bin/python" -m orbitra "$@"
    SH
    chmod 0755, bin/"orbitra"
  end

  test do
    assert_match "ORBITRA", shell_output("#{bin}/orbitra --help 2>&1", 0)
  end
end
