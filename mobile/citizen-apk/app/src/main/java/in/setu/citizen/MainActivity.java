package in.setu.citizen;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;

import java.util.Collections;

/**
 * Sideload shell around the hosted citizen PWA. Not a Play Store listing and
 * not a native rewrite — Chrome Custom Tabs / TWA would keep web-push, but
 * this WebView is fullscreen with no address bar, which is the point of a
 * demo APK. FCM getToken() may fail here (PushManager is a browser API);
 * the installed PWA in Chrome remains the path that proves delivery.
 *
 * Session tokens: the hosted PWA used sessionStorage, which dies with the
 * WebView. SESSION_SHIM mirrors those keys into localStorage before React
 * boots, so closing the app does not log the citizen out.
 */
public class MainActivity extends Activity {
    /**
     * Runs at document-start against the live Vercel bundle (still on
     * sessionStorage) and remains harmless after the PWA switches to
     * localStorage: both stores stay in sync for the two session keys.
     */
    private static final String SESSION_SHIM =
            "(function(){try{"
                + "var A='setu_citizen_token',R='setu_citizen_refresh';"
                + "var set=Storage.prototype.setItem,rem=Storage.prototype.removeItem;"
                + "var a=localStorage.getItem(A),r=localStorage.getItem(R);"
                + "if(a)set.call(sessionStorage,A,a);"
                + "if(r)set.call(sessionStorage,R,r);"
                + "Storage.prototype.setItem=function(k,v){"
                    + "set.call(this,k,v);"
                    + "if(k!==A&&k!==R)return;"
                    + "if(this===sessionStorage)set.call(localStorage,k,v);"
                    + "else if(this===localStorage)set.call(sessionStorage,k,v);"
                + "};"
                + "Storage.prototype.removeItem=function(k){"
                    + "rem.call(this,k);"
                    + "if(k!==A&&k!==R)return;"
                    + "rem.call(localStorage,k);rem.call(sessionStorage,k);"
                + "};"
            + "}catch(e){}})();";

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            getWindow().setStatusBarColor(Color.parseColor("#f3f2f1"));
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        }

        webView = new WebView(this);
        webView.setBackgroundColor(Color.parseColor("#f3f2f1"));
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setGeolocationEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            settings.setSafeBrowsingEnabled(true);
        }

        CookieManager.getInstance().setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        }

        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            WebViewCompat.addDocumentStartJavaScript(
                    webView, SESSION_SHIM, Collections.singleton("*"));
        }

        if (BuildConfig.DEBUG) {
            WebView.setWebContentsDebuggingEnabled(true);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return false;
            }

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
                    view.evaluateJavascript(SESSION_SHIM, null);
                }
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(
                    String origin, GeolocationPermissions.Callback callback) {
                callback.invoke(origin, true, false);
            }
        });

        requestLocationIfNeeded();

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(BuildConfig.PWA_URL);
        }
    }

    private void requestLocationIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            return;
        }
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED) {
            return;
        }
        requestPermissions(
                new String[] {
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                },
                1);
    }

    @Override
    protected void onPause() {
        CookieManager.getInstance().flush();
        webView.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
    }

    @Override
    protected void onDestroy() {
        CookieManager.getInstance().flush();
        super.onDestroy();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }
}
