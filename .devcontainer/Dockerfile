FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

# The upstream image currently includes a Yarn apt source that can fail
# signature verification in Codespaces feature installation.
RUN rm -f /etc/apt/sources.list.d/yarn.list
