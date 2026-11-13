# DevOps Project Scaffolding Tool

## Overview

This project is an automated Python-based command-line interface (CLI) tool designed to bootstrap production-ready PHP and Symfony applications. It eliminates manual setup friction, enforces strict environment parity between the host machine and containerized runtimes, implements professional version control practices, and provisions an automated Continuous Integration (CI) pipeline from scratch.

Built with a strong focus on reliability, security, and developer experience (DevOps UX), this script manages the complete application lifecycle from local architecture generation to remote GitHub publication.

---

## Technical Stack and Architecture

- **Language:** Python 3 (CLI automation, subprocess execution, secure error handling)
- **Framework:** PHP / Symfony (Skeleton)
- **Containerization:** Docker, Docker Compose, Nginx (FastCGI proxy server)
- **Database:** Optional MySQL 8.0 with custom port mapping to prevent host environment conflicts
- **Version Control:** Git (Git Flow branching strategy utilizing `main` and `develop`)
- **Remote and CI/CD:** GitHub CLI (`gh`) and GitHub Actions (Automated CI pipeline)

---

## Core Features and Engineering Principles

### 1. Dynamic Environment Parity

A common challenge in local development is version mismatch between the host machine and containerized environments. This script detects the exact major and minor version of PHP installed on the host machine using regular expressions (`php -v`) and dynamically injects that exact version into the generated `Dockerfile`, guaranteeing consistency.

### 2. Professional Containerization and Entrypoint Pattern

Rather than launching containers blindly, the tool generates a robust container setup adhering to industry standards:

- **Multi-Stage Dockerfile:** Pulls Composer cleanly from official multi-stage images rather than executing fragile manual installation scripts.
- **`docker-entrypoint.sh`:** A custom entrypoint script acting as a container gatekeeper. It checks whether the `vendor/` directory exists upon startup and automatically triggers `composer install` if dependencies are missing before starting the application.
- **Port Conflict Mitigation:** Maps MySQL to port `3307` on the host (`3307:3306`) to prevent collisions with pre-existing local MySQL instances.

### 3. Git Flow and Branching Strategy

To align with professional software engineering workflows, the script initializes a local Git repository, sets the default branch name to `main`, creates an initial commit, and immediately establishes and switches to a working `develop` branch.

### 4. Automated GitHub Integration and CI Pipeline

- **Repository Provisioning:** Uses the GitHub CLI (`gh`) to create a remote repository (Public or Private based on user configuration) and pushes both `main` and `develop` branches.
- **Continuous Integration (GitHub Actions):** Automatically generates a `.github/workflows/ci.yml` configuration file. Every push or pull request triggers an automated runner on GitHub that installs PHP, caches Composer dependencies for performance, and executes strict PHP syntax verification (`php -l`).

### 5. Transactional Rollback and Error Handling

To prevent half-baked directories or corrupted states if an operation fails midway (such as a network interruption during execution), the entire generation workflow is wrapped in a secure error-handling block. If any critical exception occurs, the script automatically cleans up and deletes the incomplete project directory (`shutil.rmtree`), allowing the user to retry safely without manual clean-up.

---

## Prerequisites

Before running the script, ensure the following dependencies are installed and configured on your host machine:

1. **PHP:** Installed locally (via Homebrew or package manager).
2. **Composer:** Available globally or downloadable automatically by the script.
3. **Docker and Docker Desktop:** Installed and actively running in the background.
4. **GitHub CLI (`gh`):** Installed and authenticated (`gh auth login`).

---

## Installation and Usage Guide

1. Place the generator script (`main.py`) in your local workspace directory.
2. Execute the script using Python 3:

    ```bash
    python3 main.py
    ```

3. Follow the interactive CLI prompts:
    - Enter your target project name (e.g., `my_devops_project`).
    - Select the GitHub repository visibility (`1` for Public, `2` for Private).
    - Choose whether to include a containerized MySQL database.
4. Once completed successfully, navigate into your newly generated project folder:

    ```bash
    cd my_devops_project
    ```


---

## Local Development Workflow

To start your local development environment using Docker Compose:

```bash
docker compose up -d
```

- **Web Application:** Open your browser and access `http://localhost:8080`.
- **Database (if selected):** Accessible on port `3307`.

---

## CI/CD Pipeline Breakdown

The generated `.github/workflows/ci.yml` pipeline executes the following automated steps on GitHub:

1. **Checkout:** Pulls the repository source code.
2. **Setup PHP:** Installs the synchronized PHP version along with required extensions (`intl`, `pdo`, `pdo_mysql`, `zip`).
3. **Composer Caching:** Restores cached `vendor` directories based on `composer.lock` hashes to accelerate build times.
4. **Build:** Runs non-interactive dependency installation.
5. **Test:** Validates codebase syntax integrity.