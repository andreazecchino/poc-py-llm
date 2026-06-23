# poc-py-llm

An end-to-end GitOps implementation for deploying efficient LLM inference on resource-constrained hardware, from code commit to production.

## Overview

This project showcases a setup for running large language models efficiently on resource-limited infrastructure. It combines a lightweight API layer, containerized deployment, automated infrastructure reconciliation, and observability into a cohesive system. See [https://github.com/andreazecchino/homelab](https://github.com/andreazecchino/homelab) for infrastructure details.

## Architecture

### AI Core
- **FastAPI** handling the API layer
- **Ollama** with **Smollm2 360M** quantized 4-bit model (deployed with Kubernetes manifests in my [homelab](https://github.com/andreazecchino/homelab)) for efficient LLM inference on constrained hardware

### CI/CD Pipeline
- **GitHub Actions** workflows triggered on push events
- Automated Docker image building and publishing to **GitHub Container Registry**
- **FluxCD** for continuous deployment to my [K3s homelab](https://github.com/andreazecchino/homelab) using GitOps rules.

### Observability
- **kube-prometheus-stack** for metrics collection and monitoring

## Key Features

**Lightweight & Efficient** - 4-bit quantized models optimized for resource-constrained environments
**Containerized** - Docker-based deployment with automated image building
**Fully Automated** - CI/CD pipeline with GitOps-driven deployments
**Observable** - Complete monitoring and metrics with Prometheus and Grafana

## Tech Stack

- **Language:** Python 3
- **API Framework:** FastAPI
- **LLM Runtime:** Ollama
- **Container:** Docker
- **Orchestration:** Kubernetes (K3s)
- **GitOps:** FluxCD
- **Monitoring:** kube-prometheus-stack

## Use Cases

- Testing LLM inference on resource-constrained environments
- Demonstrating GitOps best practices with Kubernetes
- Building production-ready AI services with minimal resource footprint
- Educational reference for AI + DevOps integration
