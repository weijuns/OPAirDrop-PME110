package com.tlsu.oshareairdrop;

import android.os.Binder;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.util.Log;

import java.lang.reflect.Method;
import java.net.NetworkInterface;

/** Own the explicitly requested native test session across provider state changes. */
final class NativeNetworkLease {
    private static final String TAG = "OShareAirDrop";
    private static final String SERVICE = "com.google.android.moseyservice.IMoseyService/default";
    private static final IBinder TOKEN = new Binder();
    private static volatile boolean requested;
    private static volatile Object client;
    private static volatile boolean installed;
    private static long lastMissingLog;

    private NativeNetworkLease() {}

    static boolean ownsSession() { return requested && enabled(); }

    private static boolean enabled() {
        try {
            return "1".equals(Class.forName("android.os.SystemProperties")
                    .getMethod("get", String.class, String.class)
                    .invoke(null, "debug.opairshare.nativenet", ""));
        } catch (Throwable failure) {
            return false;
        }
    }

    static synchronized void install(Entry entry, ClassLoader loader) {
        if (installed) return;
        installed = true;
        try {
            // The tested MTK binding starts on 149 and cannot dynamically hop.
            // Choose that same real channel in the stock preparation path; all
            // subsequent daemon start, network registration and transfer work stays real.
            Method channels = loader.loadClass("boe").getDeclaredMethod("c", loader.loadClass("dcz"));
            entry.hook(channels).intercept(chain -> {
                NetworkInterface network = NetworkInterface.getByName("mosey0");
                if (requested && enabled() && network != null && network.isUp()) {
                    Log.i(TAG, "NATIVE_CHANNEL preparation uses active test channel 149");
                    return java.util.Collections.singletonList(149);
                }
                return chain.proceed();
            });
            for (String phase : new String[]{"c", "l"}) {
                for (Method method : loader.loadClass("boe").getDeclaredMethods()) {
                    if (!method.getName().equals(phase)) continue;
                    entry.hook(method).intercept(chain -> {
                        Log.i(TAG, "NATIVE_PREPARE enter " + phase);
                        Object result = chain.proceed();
                        Log.i(TAG, "NATIVE_PREPARE return " + phase + " result=" + result);
                        return result;
                    });
                }
            }
        } catch (Throwable failure) { Log.w(TAG, "NATIVE_CHANNEL preparation adaptation unavailable", failure); }
        // The old diagnostics searched only no-argument methods, missing the
        // actual stop RPC c(StopParams). Guard only our explicit native lease.
        for (String[] spec : new String[][]{{"buj", "bum"}, {"cmr", "cmu"}}) {
            try {
                Method stop = loader.loadClass(spec[0]).getDeclaredMethod("c", loader.loadClass(spec[1]));
                String name = spec[0];
                entry.hook(stop).intercept(chain -> {
                    if (requested && enabled()) {
                        Log.i(TAG, "NATIVE_LEASE suppress stop RPC " + name + ".c while requested");
                        return null;
                    }
                    return chain.proceed();
                });
                Log.i(TAG, "NATIVE_LEASE installed stop guard " + name + ".c");
            } catch (Throwable failure) {
                Log.w(TAG, "NATIVE_LEASE stop guard unavailable " + spec[0], failure);
            }
        }
        HandlerThread worker = new HandlerThread("OShareNativeLease");
        worker.start();
        Handler handler = new Handler(worker.getLooper());
        handler.post(new Runnable() {
            @Override public void run() {
                try { reconcile(); }
                catch (Throwable failure) { Log.w(TAG, "NATIVE_LEASE reconciliation failed", failure); }
                handler.postDelayed(this, 3000);
            }
        });
    }

    static synchronized void request() {
        requested = true;
        reconcile();
    }

    private static synchronized void reconcile() {
        if (!requested) return;
        if (!enabled()) {
            NativeNetworkRegistration.release();
            // Turning off the explicit test flag releases the lease normally.
            Object old = client;
            client = null;
            requested = false;
            if (old != null) {
                try { old.getClass().getMethod("b").invoke(old); }
                catch (Throwable failure) { Log.w(TAG, "NATIVE_LEASE release failed", failure); }
            }
            Log.i(TAG, "NATIVE_LEASE released");
            return;
        }
        try {
            NetworkInterface network = NetworkInterface.getByName("mosey0");
            if (client != null && network != null && network.isUp()) {
                try { NativeNetworkRegistration.reconcile(network); }
                catch (Throwable failure) { Log.w(TAG, "NATIVE_NETWORK registration failed; keeping native lease", failure); }
                return;
            }
            IBinder service = (IBinder) Class.forName("android.os.ServiceManager")
                    .getMethod("checkService", String.class).invoke(null, SERVICE);
            if (service == null || !service.isBinderAlive()) {
                client = null;
                long now = android.os.SystemClock.elapsedRealtime();
                if (now - lastMissingLog > 15000) {
                    lastMissingLog = now;
                    Log.w(TAG, "NATIVE_LEASE waiting for daemon service");
                }
                return;
            }
            ClassLoader loader = ProviderHolder.loader();
            Object active = loader.loadClass("ro").getDeclaredMethod("z").invoke(null);
            if (active == null) return;
            Method start = active.getClass().getMethod("d", int[].class, IBinder.class, byte[].class);
            // Keep both the service proxy and ownership token strongly held.
            client = active;
            start.invoke(active, new int[]{149}, TOKEN, null);
            Log.i(TAG, "NATIVE_LEASE start accepted channels=[149]");
        } catch (Throwable failure) {
            client = null;
            Log.w(TAG, "NATIVE_LEASE start failed", failure);
        }
    }
}
