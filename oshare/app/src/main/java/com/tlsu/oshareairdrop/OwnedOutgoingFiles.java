package com.tlsu.oshareairdrop;

import android.content.Context;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.BooleanSupplier;

/** Preserve the stock descriptor checks; use internal policy only for live staged sends. */
final class OwnedOutgoingFiles {
    private static final String TAG = "OShareAirDrop";
    private static final Map<String, Owner> FILES = new ConcurrentHashMap<>();
    private static final class Owner {
        final File file;
        final long length;
        final BooleanSupplier active;
        Owner(File file, BooleanSupplier active) {
            this.file = file; this.length = file.length(); this.active = active;
        }
    }

    static void install(Entry entry, ClassLoader loader) {
        try {
            Class<?> policyClass = loader.loadClass("bff");
            Object internalPolicy = policyClass.getField("b").get(null);
            Method validate = loader.loadClass("bfg").getDeclaredMethod("d", Context.class,
                    ParcelFileDescriptor.class, Uri.class, policyClass);
            entry.hook(validate).intercept(chain -> {
                if (!owns((Uri) chain.getArg(2))) return chain.proceed();
                // The original validator still verifies descriptor/path identity,
                // file type and links. Do not grant access to other app data.
                Object[] arguments = chain.getArgs().toArray();
                arguments[3] = internalPolicy;
                return chain.proceed(arguments);
            });
            Log.i(TAG, "OWNED_FILES scoped internal source policy installed");
            BridgeMessenger.execute(() -> selfTest(loader));
        } catch (Throwable failure) { Log.e(TAG, "OWNED_FILES adaptation unavailable", failure); }
    }

    static void register(File file, File directory, BooleanSupplier active) throws Exception {
        File root = new File(HostContext.get().getCacheDir(), "oshare-outgoing").getCanonicalFile();
        File parent = directory.getCanonicalFile();
        File canonical = file.getCanonicalFile();
        if (!parent.getPath().startsWith(root.getPath() + File.separator)
                || !canonical.getParentFile().equals(parent)
                || android.system.OsConstants.S_ISLNK(android.system.Os.lstat(file.getPath()).st_mode)
                || !canonical.isFile() || !canonical.canRead() || !active.getAsBoolean())
            throw new IllegalArgumentException("invalid staged outgoing file");
        FILES.put(canonical.getPath(), new Owner(canonical, active));
    }

    private static boolean owns(Uri uri) {
        if (uri == null || !"file".equals(uri.getScheme()) || uri.getPath() == null) return false;
        try {
            File candidate = new File(uri.getPath());
            String canonical = candidate.getCanonicalPath();
            if (android.system.OsConstants.S_ISLNK(android.system.Os.lstat(candidate.getPath()).st_mode)) return false;
            Owner owner = FILES.get(canonical);
            return owner != null && owner.active.getAsBoolean() && owner.file.isFile()
                    && owner.file.length() == owner.length;
        } catch (Exception failure) { return false; }
    }

    static void release(File directory) {
        if (directory == null) return;
        try {
            File canonical = directory.getCanonicalFile();
            FILES.entrySet().removeIf(entry -> canonical.equals(entry.getValue().file.getParentFile()));
        } catch (Exception failure) { Log.w(TAG, "OWNED_FILES release failed", failure); }
    }

    static InputStream open(ClassLoader loader, File file) throws Exception {
        Class<?> reader = loader.loadClass("bua");
        return (InputStream) reader.getMethod("b", Context.class, Uri.class)
                .invoke(reader.getField("a").get(null), HostContext.get(), Uri.fromFile(file));
    }

    private static void selfTest(ClassLoader loader) {
        File directory = new File(HostContext.get().getCacheDir(), "oshare-outgoing/probe-" + java.util.UUID.randomUUID());
        File file = new File(directory, "local-source-probe.bin");
        java.util.concurrent.atomic.AtomicBoolean active = new java.util.concurrent.atomic.AtomicBoolean(true);
        byte[] expected = "OPAirShare local read probe; never transmitted\n".getBytes(StandardCharsets.UTF_8);
        try {
            if (!directory.mkdirs()) throw new IllegalStateException("probe directory unavailable");
            try (FileOutputStream output = new FileOutputStream(file)) { output.write(expected); }
            boolean originalDenied = denied(loader, file);
            Log.i(TAG, "OWNED_FILES probe originalDenied=" + originalDenied);
            register(file, directory, active::get);
            byte[] actual;
            try (InputStream input = open(loader, file); java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {
                byte[] buffer = new byte[256]; int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                actual = output.toByteArray();
            }
            if (!Arrays.equals(expected, actual)) throw new IllegalStateException("probe contents differ");
            // Removing ownership must restore the stock rejection.
            active.set(false);
            boolean expiredDenied = denied(loader, file);
            release(directory);
            boolean unownedDenied = denied(loader, file);
            if (!originalDenied || !expiredDenied || !unownedDenied)
                throw new IllegalStateException("stock boundary was not enforced");
            report("PASS original=denied owned=byte_exact expired=denied unowned=denied bytes=" + actual.length, null);
        } catch (Throwable failure) { report("FAIL", failure); }
        finally { release(directory); file.delete(); directory.delete(); }
    }

    private static void report(String result, Throwable failure) {
        String message = "OWNED_FILES_SELF_TEST " + result;
        if (failure != null) message += "\n" + Log.getStackTraceString(failure);
        Log.i(TAG, message);
        if (Entry.instance != null) Entry.instance.log(Log.INFO, TAG, message);
        try (FileOutputStream output = new FileOutputStream(new File(HostContext.get().getFilesDir(), "owned-files-selftest.log"))) {
            output.write(message.getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {}
    }

    private static boolean denied(ClassLoader loader, File file) throws Exception {
        try (InputStream input = open(loader, file)) { input.read(); return false; }
        catch (InvocationTargetException failure) {
            Throwable cause = failure.getCause();
            Log.i(TAG, "OWNED_FILES probe stock reader rejected source: " + cause);
            if (!(cause instanceof java.io.IOException) && !(cause instanceof SecurityException)) throw failure;
            return true;
        }
    }
}
