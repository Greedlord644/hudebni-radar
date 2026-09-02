import { Radar } from "./radar";
import ads from "./data/ads.json";

export default function Home() {
  return <Radar data={ads} />;
}
