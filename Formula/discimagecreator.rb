# DiscImageCreator for macOS, built from source at the same upstream commit as
# fedora/discimagecreator/discimagecreator.spec (upstream publishes no macOS
# build, and the one MPF bundles is linked against MacPorts). Optical drives only:
# on macOS DIC opens drives through SCSITaskAuthoringDevice, which a floppy is not.
#
# DIC finds its helpers (EccEdc, DVDAuth, unscrambler) next to its own executable
# path, and on macOS that path is the one it was started by, symlink or not. So
# everything lives in libexec and bin/ holds scripts that exec the real files.
class Discimagecreator < Formula
  desc "Low-level disc dumper plus EccEdc / DVDAuth / unscrambler helpers"
  homepage "https://github.com/saramibreak/DiscImageCreator"
  url "https://github.com/saramibreak/DiscImageCreator/archive/9269234aab5042d4cfe2e62374a8fa1ab31e98df.tar.gz"
  version "20260913144738.9269234a"
  sha256 "d2bb8ab1abb021d62d794771e953c6b535c26e585f810fcee909d7714b196901"
  license all_of: ["Apache-2.0", "GPL-3.0-or-later", "GPL-2.0-or-later"]
  revision 1

  depends_on "pkgconf" => :build
  depends_on "libarchive"
  depends_on :macos
  depends_on "openssl@3"

  uses_from_macos "zlib"

  resource "eccedc" do
    url "https://github.com/saramibreak/EccEdc/archive/427dd5713718f5a4d2f500da0ce457ce1bebd8a2.tar.gz"
    sha256 "0735eaa9cfb3f87deafd253f969ebfbaeaf53ba6fa31a6f9de77bac7d16ce93b"
  end

  resource "dvdauth" do
    url "https://github.com/saramibreak/DVDAuth/archive/708cf70429877d44619260feafa437d65b2994a1.tar.gz"
    sha256 "22c873e1742838470df4e46c3929d7b5ab28b79902b51f5259538c8297bb5377"
  end

  resource "unscrambler" do
    url "https://github.com/saramibreak/unscrambler/archive/ffbf48a271e734c8fd34128d76d4c0b6c51f541f.tar.gz"
    sha256 "a9cc9e6e440dc9c143dea4a2334b20a8d3ca90035b23af76eed53a2f9a532f3a"
  end

  def install
    # DIC reads driveOffset.txt, default.dat and friends from two fixed paths,
    # neither of which is Homebrew's on Apple Silicon. Point both at this keg
    # (inreplace fails the build if upstream moves them). The lookup buffer is
    # 128 bytes; the opt path plus the longest file name stays well below.
    data = "#{opt_share}/DiscImageCreator/"
    inreplace %w[DiscImageCreator/get.cpp DiscImageCreator/xml.cpp] do |s|
      s.gsub! "/usr/local/share/DiscImageCreator/", data
      s.gsub! "/usr/share/DiscImageCreator/", data
    end
    # DIC's own makefile, not meson.build: both list the same sources
    # (compared 2026-10-13; a file the makefile lacks fails the link here),
    # and the makefile's Darwin branch finds libarchive, zlib and openssl
    # through pkg-config. meson runs on Homebrew's Python, which needs
    # openssl@4, and on Intel Macs Homebrew 7 ships no bottles, so a build
    # tool would compile a second OpenSSL that DIC never links (on test-macos
    # that build failed, 2026-10-13). The makefile's GCC-only warning flags
    # are only warnings under clang.
    system "make", "-C", "DiscImageCreator", "CC=#{ENV.cc}", "CXX=#{ENV.cxx}"
    libexec.install "DiscImageCreator/DiscImageCreator" => "DiscImageCreator.out"
    # What meson.build installs, plus the drive sheet the Fedora spec adds.
    (share/"DiscImageCreator").install %w[
      default.dat driveOffset.txt C2ErrorProtect.txt ReadErrorProtect.txt
    ].map { |f| "Release_ANSI/#{f}" }
    (share/"DiscImageCreator").install "Release_ANSI/DVDRawBruteforce - Drive Sheet - Sheet1.tsv"

    resource("eccedc").stage do
      system "make", "-C", "EccEdc", "CC=#{ENV.cc}", "CXX=#{ENV.cxx}"
      libexec.install "EccEdc/EccEdc.out"
    end
    resource("dvdauth").stage do
      # libdvdcpxm/src carries its own stdint.h (fixed-width typedefs plus
      # byte-swap macros), included as "stdint.h". The makefile puts that
      # directory on the -I path, so libc++'s <cstdint> finds it too instead of
      # the real <stdint.h> and stops ("tried including <stdint.h> but didn't
      # find libc++'s", CI 2026-10-13, both architectures). -iquote keeps it
      # for "..." includes only.
      # The makefile also adds the SDK's Frameworks directory as an -I path,
      # because DVDAuth spells framework headers as paths
      # (<IOKit.framework/Headers/...>). Spell them the way DIC's own copy of
      # this header does (<IOKit/...>), which clang resolves by itself.
      inreplace "DVDAuth/_linux/defineForLinux.h" do |s|
        s.gsub! "CoreFoundation.framework/Headers/CFPluginCOM.h", "CoreFoundation/CFPlugInCOM.h"
        s.gsub! "CoreFoundation.framework/Headers/", "CoreFoundation/"
        s.gsub! "IOKit.framework/Headers/", "IOKit/"
        s.gsub! "Kernel.framework/Headers/IOKit/", "IOKit/"
      end
      inreplace "DVDAuth/libdvdcpxm/src/dvd_command.h", "Kernel.framework/Headers/IOKit/", "IOKit/"
      system "make", "-C", "DVDAuth", "CC=#{ENV.cc}", "CXX=#{ENV.cxx}",
             "INCFLAGS=-I. -iquote libdvdcpxm/src -I_linux",
             "LIBS=-framework CoreFoundation -framework IOKit"
      libexec.install "DVDAuth/DVDAuth.out"
    end
    resource("unscrambler").stage do
      system "make", "CC=#{ENV.cc}", "CXX=#{ENV.cxx}"
      libexec.install "unscrambler.out"
    end

    {
      "discimagecreator" => "DiscImageCreator.out",
      "dic"              => "DiscImageCreator.out",
      "eccedc"           => "EccEdc.out",
      "dvdauth"          => "DVDAuth.out",
      "unscrambler"      => "unscrambler.out",
    }.each do |name, target|
      (bin/name).write <<~SH
        #!/bin/bash
        exec "#{opt_libexec}/#{target}" "$@"
      SH
      (bin/name).chmod 0755
    end
  end

  def caveats
    <<~EOS
      macOS: optical drives only, no floppy. Name the drive by its BSD name,
      as `diskutil list` shows it (for example disk4).
    EOS
  end

  test do
    # Without arguments DIC prints its version and usage after two Enter keys.
    assert_match "AppVersion", pipe_output(bin/"discimagecreator", "\n\n")
    %w[default.dat driveOffset.txt C2ErrorProtect.txt ReadErrorProtect.txt].each do |data|
      assert_path_exists share/"DiscImageCreator"/data
    end
    %w[EccEdc.out DVDAuth.out unscrambler.out].each do |helper|
      assert_predicate libexec/helper, :executable?
    end
  end
end
