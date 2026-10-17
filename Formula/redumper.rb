# redumper for macOS: upstream's own release build, repackaged. It ships its own
# libc++ in lib/ and finds it through RPATH @executable_path/../lib, so bin/ and
# lib/ stay together under libexec, and bin/redumper is a script that execs the
# real file (a symlink would hand the loader the wrong @executable_path).
#
# Homebrew allows no per-architecture url in a formula, only a per-architecture
# resource. So the url is the source tarball of the same tag -- it carries the
# LICENSE and README the binary zips lack, and Homebrew installs both -- and
# the binary comes from the resource for this machine.
#
# The build number follows fedora/redumper/redumper.spec: the same watcher bumps
# every lane in one commit.
class Redumper < Formula
  desc "Low-level byte-perfect CD disc dumper"
  homepage "https://github.com/superg/redumper"
  url "https://github.com/superg/redumper/archive/refs/tags/b766.tar.gz"
  sha256 "8268d52a00eb50212d365b388d3d74919444c388667ff9306cdcb7ec5ce23262"
  license "GPL-3.0-only"

  depends_on :macos

  resource "binary" do
    on_arm do
      url "https://github.com/superg/redumper/releases/download/b766/redumper-b766-macos-arm64.zip"
      sha256 "0df4fd07ebafc0ab364804ac8e9f50cee620c1d299e95c78c08271ced96c61c9"
    end
    on_intel do
      url "https://github.com/superg/redumper/releases/download/b766/redumper-b766-macos-x64.zip"
      sha256 "5af597b057fb30834c5aa1e84ff358cc381250eeb2a7d4b080dbc49a5fd143f4"
    end
  end

  def install
    resource("binary").stage do
      libexec.install "bin", "lib"
    end
    bin.write_exec_script libexec/"bin/redumper"
  end

  def caveats
    <<~EOS
      Name the drive by its BSD name, as `diskutil list` shows it:
        redumper disc --drive=disk4
      (not /dev/disk4). No root is needed. macOS refuses drive access to a
      program working inside Desktop, Documents or Downloads, so dump into
      another folder.
    EOS
  end

  test do
    assert_match "build: b#{version}", shell_output("#{bin}/redumper --version")
  end
end
