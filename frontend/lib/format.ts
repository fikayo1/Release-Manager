export function utc(value?:string|null){if(!value)return 'Not yet';return new Intl.DateTimeFormat('en',{dateStyle:'medium',timeStyle:'short',timeZone:'UTC'}).format(new Date(value))+' UTC'}
