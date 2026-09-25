import { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

type Props = {
  latitude: number | null;
  longitude: number | null;
  radiusMeters: number;
  onChange: (latitude: number, longitude: number) => void;
};

const token = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN as string | undefined;

function circle(longitude: number, latitude: number, radiusMeters: number) {
  const coordinates: number[][] = [];
  const latitudeScale = 111_320;
  const longitudeScale = latitudeScale * Math.cos(latitude * Math.PI / 180);
  for (let index = 0; index <= 64; index += 1) {
    const angle = index * 2 * Math.PI / 64;
    coordinates.push([
      longitude + Math.cos(angle) * radiusMeters / longitudeScale,
      latitude + Math.sin(angle) * radiusMeters / latitudeScale,
    ]);
  }
  return { type: 'Feature' as const, properties: {}, geometry: { type: 'Polygon' as const, coordinates: [coordinates] } };
}

export function MapboxVenuePicker({ latitude, longitude, radiusMeters, onChange }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const marker = useRef<mapboxgl.Marker | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!token || !container.current || map.current) return;
    mapboxgl.accessToken = token;
    const initial: [number, number] = longitude != null && latitude != null
      ? [longitude, latitude] : [7.4951, 9.0579];
    const instance = new mapboxgl.Map({
      container: container.current,
      style: 'mapbox://styles/mapbox/streets-v12',
      center: initial,
      zoom: longitude != null && latitude != null ? 16 : 5,
    });
    instance.addControl(new mapboxgl.NavigationControl(), 'top-right');
    instance.on('click', event => onChangeRef.current(event.lngLat.lat, event.lngLat.lng));
    map.current = instance;
    return () => { instance.remove(); map.current = null; marker.current = null; };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance || latitude == null || longitude == null) return;
    if (!marker.current) {
      marker.current = new mapboxgl.Marker({ draggable: true })
        .setLngLat([longitude, latitude])
        .addTo(instance);
      marker.current.on('dragend', () => {
        const point = marker.current!.getLngLat();
        onChangeRef.current(point.lat, point.lng);
      });
    } else marker.current.setLngLat([longitude, latitude]);
    if (!instance.loaded()) {
      instance.once('load', () => instance.flyTo({ center: [longitude, latitude], zoom: 16 }));
    } else instance.flyTo({ center: [longitude, latitude], zoom: Math.max(instance.getZoom(), 16) });
  }, [latitude, longitude]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || latitude == null || longitude == null) return;
    const update = () => {
      const data = circle(longitude, latitude, radiusMeters);
      const source = instance.getSource('venue-radius') as mapboxgl.GeoJSONSource | undefined;
      if (source) source.setData(data);
      else {
        instance.addSource('venue-radius', { type: 'geojson', data });
        instance.addLayer({ id: 'venue-radius-fill', type: 'fill', source: 'venue-radius', paint: { 'fill-color': '#0f766e', 'fill-opacity': 0.16 } });
        instance.addLayer({ id: 'venue-radius-line', type: 'line', source: 'venue-radius', paint: { 'line-color': '#0f766e', 'line-width': 2 } });
      }
    };
    if (instance.loaded()) update(); else instance.once('load', update);
  }, [latitude, longitude, radiusMeters]);

  if (!token) {
    return <p className="info-msg">Map preview is unavailable until <code>VITE_MAPBOX_ACCESS_TOKEN</code> is configured. Coordinate fields remain fully functional.</p>;
  }
  return <div ref={container} aria-label="Venue geofence map" style={{ height: 360, borderRadius: 'var(--tv-radius-md)', overflow: 'hidden', marginBottom: '1rem' }} />;
}

export default MapboxVenuePicker;
