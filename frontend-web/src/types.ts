export type Conversation={id:string;channel:string;bot_id?:string;subject:string;status:string;priority:string;assigned_to?:string;assigned_team_id?:string;automation_paused:boolean;unread_count:number;last_message_at?:string};
export type Message={id:string;direction:string;type:string;status:string;author_name:string;text?:string;internal:boolean;attempts:number;created_at:string;attachments:{id:string;filename:string;mime_type:string;size_bytes:number}[]};
export type Detail=Conversation&{messages:Message[];customer_id?:string};
export type Bot={id:string;public_id:string;name:string;username?:string;telegram_bot_id?:string;mode:string;status:string;active:boolean;token?:string;last_error?:string};
export type Outbox={id:string;conversation_id:string;message_id:string;operation:string;status:string;attempts:number;last_error?:string;created_at:string;sent_at?:string};
export type InboxEvent={id:string;bot_id:string;external_event_id:string;status:string;attempts:number;error?:string;received_at:string;processed_at?:string};
