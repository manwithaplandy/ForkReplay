export default {
  async fetch(_req: Request): Promise<Response> {
    return new Response("Workflows stub", { status: 200 });
  },
};
