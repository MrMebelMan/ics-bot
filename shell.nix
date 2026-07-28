{ pkgs ? import <nixpkgs> { } }:

let
  python = pkgs.python313;
  pythonEnv = python.withPackages (ps: with ps; [
    playwright
    python-dotenv
    requests
  ]);
in
pkgs.mkShell {
  packages = [
    pythonEnv
    pkgs.wireguard-tools
    pkgs.nssTools
  ];

  shellHook = ''
    export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=$(which chromium)
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
    export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
  '';
}
