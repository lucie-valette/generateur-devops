import os
import subprocess
import sys
import urllib.request
import re
import shutil

# --- DISPLAY UTILITIES ---

def print_banner(text):
    print("\n" + "=" * 60)
    print(text.center(60))
    print("=" * 60)

def print_info(text):
    print(f"[INFO] {text}")

def print_success(text):
    print(f"[SUCCESS] {text}")

def print_warning(text):
    print(f"[WARNING] {text}")

def print_error(text):
    print(f"[ERROR] {text}")

# --- SYSTEM & ENVIRONMENT HELPERS ---

def run_command(command, target_directory, hide_output=True):
    """Executes shell commands safely, optionally streaming raw logs for external tools."""
    try:
        if hide_output:
            subprocess.run(command, shell=True, cwd=target_directory, check=True, text=True, capture_output=True)
        else:
            print("\n" + "-" * 60)
            print(f">>> RUNNING SYSTEM PROCESS: {command}")
            print("-" * 60)

            subprocess.run(command, shell=True, cwd=target_directory, check=True)

            print("-" * 60)
            print("<<< PROCESS COMPLETED")
            print("-" * 60 + "\n")

    except subprocess.CalledProcessError as e:
        print_error(f"Command execution failed: {command}")
        if hide_output and e.stderr:
            print(e.stderr)
        sys.exit(1)

def check_php():
    """Extracts major.minor PHP version from host to keep container parity tight."""
    try:
        result = subprocess.run("php -v", shell=True, check=True, text=True, capture_output=True)
        match = re.search(r"PHP (\d+\.\d+)", result.stdout)

        if match:
            php_version = match.group(1)
            print_success(f"PHP engine found (v{php_version}).")
            return php_version
        else:
            print_warning("Could parse PHP version string. Falling back to default 8.2.")
            return "8.2"

    except subprocess.CalledProcessError:
        print_error("PHP is missing from your system path.")
        print_info("Quick fix for macOS: brew install php")
        sys.exit(1)

def check_docker():
    """Quick socket check to make sure Docker daemon is actually up and running."""
    try:
        subprocess.run("docker info", shell=True, check=True, capture_output=True)
        print_success("Docker daemon is active.")
        return True
    except subprocess.CalledProcessError:
        print_warning("Docker is either not installed or not running.")
        print_info("The project will still be generated, but without containerization.")
        return False

def check_github_cli():
    """Verifies auth tokens for gh CLI so we can push automatically later."""
    try:
        subprocess.run("gh auth status", shell=True, check=True, capture_output=True)
        print_success("GitHub CLI is authenticated.")
        return True
    except subprocess.CalledProcessError:
        return False

def setup_composer():
    """Falls back to local composer.phar if global composer isn't installed."""
    try:
        subprocess.run("composer -V", shell=True, check=True, capture_output=True)
        print_success("Global Composer utility detected.")
        return "composer"
    except subprocess.CalledProcessError:
        print_info("Global composer missing. Pulling latest composer.phar locally...")
        composer_url = "https://getcomposer.org/download/latest-stable/composer.phar"
        composer_path = os.path.join(os.getcwd(), "composer.phar")
        if not os.path.exists(composer_path):
            urllib.request.urlretrieve(composer_url, composer_path)
        print_success("Local composer.phar ready.")
        return "php composer.phar"

# --- SCAFFOLDING TEMPLATES ---

def generate_ci_workflow(target_dir, php_version):
    """Drops a GitHub Actions workflow into place for automated pull-request validation."""
    workflows_dir = os.path.join(target_dir, ".github", "workflows")
    os.makedirs(workflows_dir, exist_ok=True)

    ci_content = f"""name: CI Pipeline Symfony

on:
  push:
    branches: [ "main", "develop" ]
  pull_request:
    branches: [ "main", "develop" ]

jobs:
  build-and-test:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Setup PHP environment
      uses: shivammathur/setup-php@v2
      with:
        php-version: '{php_version}'
        extensions: intl, pdo, pdo_mysql, zip
        tools: composer:v2

    - name: Restore vendor cache
      uses: actions/cache@v3
      with:
        path: vendor
        key: ${{ runner.os }}-php-${{ hashFiles('**/composer.lock') }}
        restore-keys: |
          ${{ runner.os }}-php-

    - name: Install dependencies
      run: composer install --no-interaction --prefer-dist --optimize-autoloader

    - name: Run syntax linter
      run: find src/ -name '*.php' -exec php -l {{}} \\;
"""
    with open(os.path.join(workflows_dir, "ci.yml"), "w") as f:
        f.write(ci_content)

def generate_docker_environment(target_dir, database_type, php_version):
    """Generates Dockerfile, entrypoint bootstrap script, and a robust docker-compose stack."""
    os.makedirs(target_dir, exist_ok=True)

    # Entrypoint script handles cold starts nicely (auto-installing vendors if missing)
    entrypoint_script = """#!/bin/sh
set -e

if [ ! -f "vendor/autoload.php" ]; then
    echo "Dependencies missing inside container. Running composer install..."
    composer install --no-interaction
fi

echo "Booting up application..."
exec "$@"
"""
    with open(os.path.join(target_dir, "docker-entrypoint.sh"), "w") as f:
        f.write(entrypoint_script)

    # Clean multi-stage Dockerfile leveraging official composer binaries
    dockerfile_content = f"""FROM php:{php_version}-fpm

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

RUN apt-get update && apt-get install -y \\
    git \\
    unzip \\
    libicu-dev \\
    && docker-php-ext-install intl pdo pdo_mysql

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

WORKDIR /var/www/html

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["php-fpm"]
"""
    with open(os.path.join(target_dir, "Dockerfile"), "w") as f:
        f.write(dockerfile_content)

    # Compose setup (shifted mysql to 3307 to avoid local workstation port collisions)
    compose_content = """services:
  php:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - .:/var/www/html
    networks:
      - symfony_network

  nginx:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - .:/var/www/html
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
    depends_on:
      - php
    networks:
      - symfony_network
"""
    if database_type == "mysql":
        compose_content += """
  database:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: symfony_db
      MYSQL_USER: symfony
      MYSQL_PASSWORD: password
    ports:
      - "3307:3306"
    volumes:
      - db_data:/var/lib/mysql
    networks:
      - symfony_network

volumes:
  db_data:
"""

    compose_content += "\nnetworks:\n  symfony_network:\n"
    with open(os.path.join(target_dir, "docker-compose.yml"), "w") as f:
        f.write(compose_content)

    # Nginx virtual host mapping public front controller
    nginx_config = """server {
    listen 80;
    index index.php index.html;
    server_name localhost;
    error_log  /var/log/nginx/error.log;
    access_log /var/log/nginx/access.log;
    root /var/www/html/public;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ \\.php$ {
        try_files $uri =404;
        fastcgi_split_path_info ^(.+\\.php)(/.+)$;
        fastcgi_pass php:9000;
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_param PATH_INFO $fastcgi_path_info;
    }
}"""
    with open(os.path.join(target_dir, "nginx.conf"), "w") as f:
        f.write(nginx_config)

# --- MAIN EXECUTION ROUTINE ---

def main():
    print_banner("PHP / SYMFONY PROJECT SCAFFOLDER")
    print("This utility automates modern web app bootstrapping and infrastructure setup.")
    print("Framework target: Symfony Skeleton.\n")

    # Step 1: Gather environment prerequisites
    print_info("Phase 1: Validating local toolchain")
    php_version = check_php()
    composer_cmd = setup_composer()
    docker_ready = check_docker()
    gh_ready = check_github_cli()

    if not gh_ready:
        print("")
        print_warning("GitHub CLI ('gh') is missing or unauthenticated.")
        print_info("If you want remote repository auto-provisioning, abort now (Ctrl+C),")
        print_info("install the gh utility, and run 'gh auth login'.")
        choice = input("Proceed in LOCAL-ONLY mode? (Y/n) : ")
        if choice.lower() == "n":
            print_info("Operation canceled by user.")
            sys.exit(0)

    # Step 2: Prompt user preferences
    print_info("\nPhase 2: Project configuration")
    project_name = input("Enter project directory name (e.g. enterprise_app) : ")

    base_dir = os.getcwd()
    target_dir = os.path.join(base_dir, project_name)

    if os.path.exists(target_dir):
        print_error(f"Target directory '{project_name}' already exists.")
        sys.exit(1)

    visibility_choice = "1"
    if gh_ready:
        visibility_choice = input("GitHub repository visibility? (1: Public, 2: Private) : ")

    database_choice = ""
    if docker_ready:
        print_info("Include a MySQL service container?")
        db_input = input("Choice (1: None, 2: MySQL 8.0) : ")
        if db_input == "2":
            database_choice = "mysql"

    # Step 3 & 4: Protected transactional workflow (handles automatic cleanup on failure)
    try:
        print_info("\nPhase 3: Downloading Symfony skeleton framework")
        run_command(f"{composer_cmd} create-project symfony/skeleton {project_name}", base_dir, hide_output=False)
        print_success("Symfony scaffolding downloaded successfully.")

        print_info("\nPhase 4: Injecting infrastructure and version control configurations")
        if docker_ready:
            print_info("Writing Docker containers and entrypoint scripts...")
            generate_docker_environment(target_dir, database_choice, php_version)
            print_success("Docker environment built and synced with local PHP version.")

        if gh_ready:
            print_info("Generating GitHub Actions CI pipeline...")
            generate_ci_workflow(target_dir, php_version)
            print_success("CI pipeline file placed (.github/workflows/ci.yml).")

        # Drop a clean baseline README
        with open(os.path.join(target_dir, "README.md"), "w") as f:
            f.write(f"# {project_name}\n\nAutomated PHP/Symfony application workspace.")

        # Initialize git tracking, establish clean branching strategy (main / develop)
        print_info("Setting up local Git branches (main & develop)...")
        run_command("git init", target_dir)
        run_command("git branch -m main", target_dir)
        run_command("git add .", target_dir)
        run_command('git commit -m "chore: initial project scaffolding"', target_dir)
        run_command("git checkout -b develop", target_dir)
        print_success("Git repository initialized. Current active branch: develop.")

        # Step 5: Remote provisioning and sync
        if gh_ready:
            print_info("\nPhase 5: Provisioning remote repository on GitHub")
            flag = "--private" if visibility_choice == "2" else "--public"
            vis_label = "private" if visibility_choice == "2" else "public"

            print_info(f"Creating remote {vis_label} repository...")
            run_command(f"gh repo create {project_name} {flag} --source=. --remote=origin", target_dir, hide_output=False)

            print_info("Pushing tracking branches to remote...")
            run_command("git push -u origin main", target_dir, hide_output=False)
            run_command("git push -u origin develop", target_dir, hide_output=False)
            print_success("Remote repository successfully synchronized.")

    except Exception as unexpected_error:
        print_error("A critical error interrupted the setup routine.")
        print_info("Cleaning up partial files to keep workspace tidy...")

        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
            print_info(f"Purged incomplete directory '{project_name}'.")

        print_error("Aborted safely. You can inspect the issue and retry anytime.")
        sys.exit(1)

    # Step 6: Post-run cleanup and instructions
    if composer_cmd == "php composer.phar":
        os.remove(os.path.join(base_dir, "composer.phar"))
        print_info("Cleaned up temporary composer.phar binary from root.")

    print_banner("SETUP FINISHED SUCCESSFULLY")
    print("Your environment is fully configured. Next steps:\n")
    print(f"1. Jump into your workspace folder:")
    print(f"   cd {project_name}\n")

    if docker_ready:
        print("2. Boot up local containers in detached mode:")
        print("   docker compose up -d\n")
        print("3. Preview your application in the browser:")
        print("   http://localhost:8080\n")

if __name__ == "__main__":
    main()