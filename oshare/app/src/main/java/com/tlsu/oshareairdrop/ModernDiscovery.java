package com.tlsu.oshareairdrop;

import android.util.Log;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

/** Keep the 27391 provider's single discovery subscription shared during testing. */
final class ModernDiscovery {
    private static final String TAG = "OShareAirDrop";
    private static boolean installed;

    private ModernDiscovery() {}

    static synchronized void install(Entry entry, ClassLoader loader) throws Exception {
        if (installed) return;
        Class<?> provider = loader.loadClass("bpo");
        Class<?> options = loader.loadClass("aic");
        Class<?> callback = loader.loadClass("ajg");
        Field params = loader.loadClass("bqx").getDeclaredField("b");
        Field listener = loader.loadClass("akb").getDeclaredField("a");
        Field mode = options.getDeclaredField("a");
        Field qr = options.getDeclaredField("b");
        params.setAccessible(true);
        listener.setAccessible(true);
        mode.setAccessible(true);
        qr.setAccessible(true);

        Method start = provider.getDeclaredMethod("m", loader.loadClass("bqx"), options);
        entry.hook(start).intercept(chain -> {
            if (!Mosey27391.internalDiscovery()) {
                Object bundle = params.get(chain.getArg(0));
                Object original = listener.get(bundle);
                if (original != null && !(Proxy.isProxyClass(original.getClass())
                        && Proxy.getInvocationHandler(original) instanceof SharedCallback)) {
                    Object shared = Proxy.newProxyInstance(loader, new Class<?>[]{callback},
                            new SharedCallback(original));
                    listener.set(bundle, shared);
                    Log.i(TAG, "DISCOVERY_27391 shared callback attached to native start");
                }
            }
            return chain.proceed();
        });
        for (String name : new String[]{"h", "e"}) {
            Method stop = provider.getDeclaredMethod(name);
            entry.hook(stop).intercept(chain -> {
                if (NativeNetworkLease.ownsSession()
                        && ProviderApi.discoveryWanted(chain.getThisObject())) {
                    Log.i(TAG, "DISCOVERY_27391 retained bridge subscription on " + name);
                    return 0;
                }
                return chain.proceed();
            });
        }
        Method update = provider.getDeclaredMethod("j", options);
        entry.hook(update).intercept(chain -> {
            Object requested = chain.getArg(0);
            if (NativeNetworkLease.ownsSession() && mode.getInt(requested) != 1
                    && ProviderApi.discoveryWanted(chain.getThisObject())) {
                Object retained = options.getDeclaredConstructor(int.class, boolean.class, boolean.class)
                        .newInstance(1, qr.getBoolean(requested), false);
                Log.i(TAG, "DISCOVERY_27391 retained discovery during native idle update");
                return chain.proceed(new Object[]{retained});
            }
            return chain.proceed();
        });
        installed = true;
        entry.log(Log.INFO, TAG, "DISCOVERY_27391 shared lifecycle installed");
    }

    private static final class SharedCallback implements java.lang.reflect.InvocationHandler {
        private final Object nativeCallback;
        SharedCallback(Object callback) { nativeCallback = callback; }

        @Override public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            switch (method.getName()) {
                case "toString": return "OShare27391SharedCallback";
                case "hashCode": return System.identityHashCode(proxy);
                case "equals": return args != null && proxy == args[0];
                default:
            }
            Object result = null;
            Throwable failure = null;
            try { result = method.invoke(nativeCallback, args); }
            catch (java.lang.reflect.InvocationTargetException wrapped) { failure = wrapped.getCause(); }
            if (ProviderApi.discoveryWanted(ProviderHolder.get())) {
                try { Mosey27391.discoveryEvent(method.getName(), args); }
                catch (Throwable bridgeFailure) { Log.w(TAG, "DISCOVERY_27391 bridge callback failed", bridgeFailure); }
            }
            if (failure != null) throw failure;
            return result;
        }
    }
}
