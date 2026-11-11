package com.tlsu.oshareairdrop;

import android.os.Binder;
import android.os.IBinder;
import android.os.IInterface;

import java.lang.reflect.Method;

/**
 * ExternalProvider bridge for Mosey 1.0.927074190 (versionCode 27391).
 *
 * <p>Starting with this build the provider contract moved from the {@code cad} facade to the
 * {@code bpo} ExternalProvider implementation, and the GMS callback types were renamed. The
 * protocol itself is unchanged: discovery uses GMS Nearby Sharing options plus an
 * {@code IShareTargetDiscoveredCallback} binder, advertising and sending use
 * {@code AdvertisingOptions} plus the {@code ais} transfer callback.
 */
final class Mosey27391 {
    private static final String TAG = "OShareAirDrop";
    private static final String DISCOVERED =
            "com.google.android.gms.nearby.sharing.internal.IShareTargetDiscoveredCallback";
    private static final String STATUS = "com.google.android.gms.common.api.internal.IStatusCallback";
    private static final ThreadLocal<Boolean> INTERNAL_DISCOVERY = ThreadLocal.withInitial(() -> false);

    static boolean internalDiscovery() { return INTERNAL_DISCOVERY.get(); }

    private Mosey27391() {}

    static boolean supported(ClassLoader loader) {
        try {
            loader.loadClass("aic");
            loader.loadClass("bqx");
            loader.loadClass("akb");
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    /** A local binder whose in-process interface is our proxy, not an AIDL stub. */
    private static final class LocalBinder extends Binder {
        private final String descriptor;
        private final IInterface local;

        LocalBinder(String descriptor, Object proxy) {
            this.descriptor = descriptor;
            this.local = (IInterface) proxy;
        }

        @Override
        public IInterface queryLocalInterface(String name) {
            return descriptor.equals(name) ? local : null;
        }
    }

    static Object discoveryEvent(String method, Object[] args) throws Throwable {
        Object wrapper = args != null && args.length > 0 ? args[0] : null;
        if (wrapper == null) return null;
        Object target = ProviderApi.wrapperTarget(wrapper);
        if (target == null) return null;
        switch (method) {
            case "e": // onDiscovered
                ProviderApi.targetFound(target);
                break;
            case "h": // onUpdated
                ProviderApi.targetUpdated(target);
                break;
            case "g": // onLost
                ProviderApi.targetLost(target);
                break;
            default:
                break;
        }
        return null;
    }

    private static Object statusEvent(String method, Object[] args) {
        return null;
    }

    private static Object transferEvent(String method, Object[] args) {
        return ProviderApi.transferEvent(args);
    }

    private static Object advertisingOptions(ClassLoader loader, String name) throws Throwable {
        Class<?> options = loader.loadClass("aib");
        return options.getDeclaredConstructor(int.class, String.class, boolean.class, boolean.class)
                .newInstance(0, name, true, false);
    }

    static int startDiscovery(ClassLoader loader, Object provider) throws Throwable {
        Object callback = CallbackFactory.create(loader, "ajg", Mosey27391::discoveryEvent);
        Object status = CallbackFactory.create(loader, "acq", Mosey27391::statusEvent);
        Class<?> aic = loader.loadClass("aic");
        Object options = aic.getDeclaredConstructor(int.class, boolean.class, boolean.class)
                .newInstance(1, false, false);
        Class<?> akb = loader.loadClass("akb");
        Object params = akb.getDeclaredConstructor(IBinder.class, aic, IBinder.class)
                .newInstance(new LocalBinder(DISCOVERED, callback), options,
                        new LocalBinder(STATUS, status));
        Class<?> bqx = loader.loadClass("bqx");
        Object holder = bqx.getDeclaredConstructor(loader.loadClass("aiv"), akb)
                .newInstance(null, params);
        Method start = provider.getClass().getMethod("m", bqx, aic);
        boolean previous = INTERNAL_DISCOVERY.get();
        INTERNAL_DISCOVERY.set(true);
        try { return ((Number) start.invoke(provider, holder, options)).intValue(); }
        finally { INTERNAL_DISCOVERY.set(previous); }
    }

    static int stopDiscovery(Object provider) throws Throwable {
        Method stop = provider.getClass().getMethod("h");
        return ((Number) stop.invoke(provider)).intValue();
    }

    static int startAdvertising(ClassLoader loader, Object provider, String name) throws Throwable {
        Object options = advertisingOptions(loader, name);
        Object callback = CallbackFactory.create(loader, "ais", Mosey27391::transferEvent);
        Method start = provider.getClass().getMethod("f", options.getClass(), loader.loadClass("ais"));
        return ((Number) start.invoke(provider, options, callback)).intValue();
    }

    static int updateAdvertising(ClassLoader loader, Object provider, String name) throws Throwable {
        Object options = advertisingOptions(loader, name);
        Method update = provider.getClass().getMethod("i", options.getClass());
        return ((Number) update.invoke(provider, options)).intValue();
    }

    static int stopAdvertising(Object provider) throws Throwable {
        Method stop = provider.getClass().getMethod("g");
        return ((Number) stop.invoke(provider)).intValue();
    }

    static int send(ClassLoader loader, Object provider, String deviceName, Object target,
            CallbackFactory.Handler handler) throws Throwable {
        Object callback = CallbackFactory.create(loader, "ais", handler);
        Method send = provider.getClass().getMethod("d", String.class, target.getClass(),
                loader.loadClass("ais"));
        return ((Number) send.invoke(provider, deviceName, target, callback)).intValue();
    }

    static int accept(Object provider, Object target) throws Throwable {
        Method accept = provider.getClass().getMethod("a", target.getClass());
        return ((Number) accept.invoke(provider, target)).intValue();
    }

    static int cancel(Object provider, Object target) throws Throwable {
        Method cancel = provider.getClass().getMethod("b", target.getClass());
        return ((Number) cancel.invoke(provider, target)).intValue();
    }

    static int deny(Object provider, Object target) throws Throwable {
        Method deny = provider.getClass().getMethod("c", target.getClass());
        return ((Number) deny.invoke(provider, target)).intValue();
    }
}
