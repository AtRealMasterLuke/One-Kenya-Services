// Location picker for the report form. Progressive enhancement: without JavaScript the
// ward dropdown still works. The map library (~40 KB) is only fetched if the citizen asks
// for the map, to save data on slow connections.
(function () {
  "use strict";

  var MURANGA_CENTRE = [-0.78, 37.0];
  var lat = document.getElementById("id_latitude");
  var lng = document.getElementById("id_longitude");
  var status = document.getElementById("location-status");
  var useBtn = document.getElementById("use-location");
  var mapBtn = document.getElementById("show-map");
  var mapEl = document.getElementById("map");
  var script = document.currentScript || document.querySelector("script[data-leaflet-js]");
  var map = null;
  var marker = null;

  function setPoint(latitude, longitude, how) {
    lat.value = latitude.toFixed(6);
    lng.value = longitude.toFixed(6);
    status.textContent = "Location set " + how + ": " + lat.value + ", " + lng.value + ".";
    status.classList.add("ok");
    if (map) {
      if (!marker) marker = window.L.marker([latitude, longitude]).addTo(map);
      else marker.setLatLng([latitude, longitude]);
    }
  }

  function loadLeaflet(done) {
    if (window.L) return done();
    var tag = document.createElement("script");
    tag.src = script.getAttribute("data-leaflet-js");
    tag.onload = done;
    tag.onerror = function () { status.textContent = "The map couldn't load. Use your location or choose the ward."; };
    document.head.appendChild(tag);
  }

  function showMap() {
    mapEl.hidden = false;
    mapBtn.hidden = true;
    status.textContent = "Loading map…";
    loadLeaflet(function () {
      var L = window.L;
      var start = lat.value ? [parseFloat(lat.value), parseFloat(lng.value)] : MURANGA_CENTRE;
      map = L.map(mapEl).setView(start, lat.value ? 17 : 10);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
        referrerPolicy: "strict-origin-when-cross-origin" // OSM's tile policy requires a Referer
      }).addTo(map);
      if (lat.value) setPoint(parseFloat(lat.value), parseFloat(lng.value), "earlier");
      else status.textContent = "Tap the map where the problem is.";
      map.on("click", function (e) { setPoint(e.latlng.lat, e.latlng.lng, "on the map"); });
    });
  }

  function useLocation() {
    status.textContent = "Finding your location…";
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        var accuracy = Math.round(pos.coords.accuracy);
        setPoint(pos.coords.latitude, pos.coords.longitude, "from your phone (accurate to about " + accuracy + " m)");
        if (map) map.setView([pos.coords.latitude, pos.coords.longitude], 17);
      },
      function () {
        status.textContent = "We couldn't get your location. Tap the map instead, or choose the ward.";
        if (!map) showMap();
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    );
  }

  if ("geolocation" in navigator) {
    useBtn.hidden = false;
    useBtn.addEventListener("click", useLocation);
  }
  mapBtn.hidden = false;
  mapBtn.addEventListener("click", showMap);
  if (lat.value && lng.value) {
    status.textContent = "Location set: " + lat.value + ", " + lng.value + ".";
    status.classList.add("ok");
  }
})();
