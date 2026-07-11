// The built-in cast. Adding a character later = drop a folder in
// public/characters/ and add one line here. No other code changes.
export interface CharacterInfo {
  id: string;
  name: string;
  blurb: string;
}

export const CHARACTERS: CharacterInfo[] = [
  { id: "berry", name: "Berry", blurb: "The Strawvarie mascot." },
  { id: "drip", name: "Drip", blurb: "A cheerful water droplet." },
  { id: "sprout", name: "Sprout", blurb: "A leafy little sprout." },
];

export const characterDir = (id: string) => `characters/${id}`;
