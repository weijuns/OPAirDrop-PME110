package com.tlsu.oshareairdrop;

import android.os.Binder;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.util.Log;

import java.lang.reflect.Method;
import java.net.NetworkInterface;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;

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

    static String diagnostics() {
        try {
            Object provider = ProviderHolder.get();
            Object controller = provider.getClass().getField("a").get(provider);
            Class<?> type = controller.getClass();
            Object slot = type.getField("i").get(controller);
            Object job = slot.getClass().getField("a").get(slot);
            java.lang.reflect.Field running = type.getDeclaredField("H");
            running.setAccessible(true);
            android.net.wifi.WifiManager wifi = (android.net.wifi.WifiManager) type.getField("g").get(controller);
            ClassLoader loader = ProviderHolder.loader();
            return "requested=" + requested + " ready=" + realSessionReady()
                    + " wifi=" + wifi.isWifiEnabled() + " wifiState=" + wifi.getWifiState()
                    + " controllerRunning=" + running.getBoolean(controller)
                    + " channels=" + type.getField("o").get(controller)
                    + " startJob=" + job + " modernStart=" + loader.loadClass("cyp").getMethod("o").invoke(null)
                    + " completionEvent=" + loader.loadClass("cyz").getMethod("d").invoke(null);
        } catch (Throwable failure) { return "unavailable=" + failure; }
    }

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
                    entry.log(Log.INFO, TAG, "NATIVE_CHANNEL preparation uses active test channel 149");
                    return java.util.Collections.singletonList(149);
                }
                entry.log(Log.INFO, TAG, "NATIVE_CHANNEL stock preparation requested=" + requested
                        + " iface=" + (network != null));
                return chain.proceed();
            });
            for (String phase : new String[]{"c", "l"}) {
                for (Method method : loader.loadClass("boe").getDeclaredMethods()) {
                    if (!method.getName().equals(phase)) continue;
                    entry.hook(method).intercept(chain -> {
                        entry.log(Log.INFO, TAG, "NATIVE_PREPARE enter " + phase);
                        Object result = chain.proceed();
                        entry.log(Log.INFO, TAG, "NATIVE_PREPARE return " + phase + " result=" + result);
                        return result;
                    });
                }
            }
        } catch (Throwable failure) { Log.w(TAG, "NATIVE_CHANNEL preparation adaptation unavailable", failure); }
        // A live interface is not a completed controller start. In particular,
        // boe.l also configures the daemon, registers its network and enqueues
        // the completion event. Let the original coroutine finish every time.
        entry.log(Log.INFO, TAG, "NATIVE_PREPARE preserving stock startup and completion");
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
        // This runs on OShareAutoDiscovery, never the UI thread. Wait for the
        // daemon's asynchronous interface creation and network registration
        // before discovery queues a stock controller preparation coroutine.
        long deadline = android.os.SystemClock.elapsedRealtime() + 6000;
        while (enabled() && !realSessionReady()
                && android.os.SystemClock.elapsedRealtime() < deadline) {
            try { Thread.sleep(100); }
            catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); break; }
            reconcile();
        }
        if (Entry.instance != null) Entry.instance.log(Log.INFO, TAG,
                "NATIVE_LEASE admission ready=" + realSessionReady());
    }

    private static boolean realSessionReady() {
        if (!requested || !enabled() || client == null) return false;
        try {
            IBinder service = (IBinder) Class.forName("android.os.ServiceManager")
                    .getMethod("checkService", String.class).invoke(null, SERVICE);
            NetworkInterface iface = NetworkInterface.getByName("mosey0");
            if (service == null || !service.isBinderAlive() || iface == null || !iface.isUp()
                    || iface.getInterfaceAddresses().isEmpty()) return false;
            ConnectivityManager manager = HostContext.get().getSystemService(ConnectivityManager.class);
            for (Network network : manager.getAllNetworks()) {
                LinkProperties properties = manager.getLinkProperties(network);
                if (properties != null && "mosey0".equals(properties.getInterfaceName())) return true;
            }
        } catch (Throwable failure) { Log.w(TAG, "NATIVE_PREPARE lease readiness failed", failure); }
        return false;
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
