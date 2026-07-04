@echo off
setlocal enabledelayedexpansion

rem ============================================================
rem new-branch.bat
rem Creates a branch from a GitHub issue, links the card to the
rem branch, bumps the version, and logs it in CHANGELOG.md.
rem
rem usage: new-branch.bat issue-number [minor|patch|major]
rem        bump type defaults to minor if omitted
rem
rem requires: gh (GitHub CLI, authenticated), cargo-edit
rem ============================================================

if "%~1"=="" (
    echo usage: new-branch.bat issue-number [minor^|patch^|major]
    exit /b 1
)

set ISSUE=%~1
set BUMP=%~2
if "%BUMP%"=="" set BUMP=minor

rem --- make sure gh is available ---
gh --version >nul 2>&1
if errorlevel 1 (
    echo GitHub CLI ^(gh^) not found. Install it and run: gh auth login
    exit /b 1
)

rem --- make sure cargo-edit is available (provides cargo set-version) ---
cargo set-version --help >nul 2>&1
if errorlevel 1 (
    echo cargo-edit not found, installing...
    cargo install cargo-edit
    if errorlevel 1 (
        echo failed to install cargo-edit, aborting.
        exit /b 1
    )
)

rem --- refuse to run with uncommitted changes ---
git diff --quiet
if errorlevel 1 (
    echo working tree has uncommitted changes, commit or stash first.
    exit /b 1
)

rem --- fetch the issue title (for the changelog line) ---
set TITLE=
for /f "usebackq delims=" %%t in (`gh issue view %ISSUE% --json title -q .title`) do set TITLE=%%t
if "!TITLE!"=="" (
    echo could not read issue #%ISSUE%, aborting.
    exit /b 1
)
echo issue #%ISSUE%: !TITLE!

rem --- create the branch, link it to the issue, and check it out ---
rem     gh names it automatically: <number>-<slugified-title>
gh issue develop %ISSUE% --checkout
if errorlevel 1 (
    echo failed to create linked branch, aborting.
    exit /b 1
)

for /f "usebackq delims=" %%b in (`git branch --show-current`) do set BRANCH=%%b
echo branch: !BRANCH!

rem --- bump the version ---
cargo set-version --bump %BUMP%
if errorlevel 1 (
    echo version bump failed, aborting.
    exit /b 1
)

for /f "tokens=2 delims== " %%v in ('findstr /r "^version" Cargo.toml') do set NEWVER=%%~v
echo new version: !NEWVER!

rem --- ensure a milestone exists for this version, then assign the issue ---
gh api repos/{owner}/{repo}/milestones -f title="v!NEWVER!" >nul 2>&1
gh issue edit %ISSUE% --milestone "v!NEWVER!"
if errorlevel 1 (
    echo warning: could not assign milestone, continuing anyway.
)

rem --- create CHANGELOG.md if it doesn't exist ---
if not exist CHANGELOG.md (
    echo # Changelog>CHANGELOG.md
    echo.>>CHANGELOG.md
)

rem --- append the changelog line ---
echo - v!NEWVER! - !TITLE! ^(#%ISSUE%^)>>CHANGELOG.md

rem --- commit ---
git add Cargo.toml Cargo.lock CHANGELOG.md
git commit -m "Start #%ISSUE% (v!NEWVER!): !TITLE!"
if errorlevel 1 (
    echo commit failed.
    exit /b 1
)

echo.
echo done: branch !BRANCH!, version !NEWVER!, issue #%ISSUE% linked.
endlocal