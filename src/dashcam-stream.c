#include "dashcam-stream.h"

static void exit_app() {
  // Prevent multiple exits
  if (exiting) {
    return;
  }
  exiting = 1;
  g_warning("Exiting...");

  // Set alarm to exit in 2 seconds if EOS fails to exit
  alarm(2);

  // Split output and EOS current stream then exit
  set_stream_state(0);
  if (main_pipeline) {
    split_output(0);
  }
}

static void create_main_pipeline() {
  GstBus *bus;
  GstCaps *main_source_caps;

  g_message("Creating main pipeline.");

  // Remove main pipeline
  if (main_pipeline) {
    gst_element_set_state(main_pipeline, GST_STATE_NULL);
    gst_object_unref(main_pipeline);
    main_pipeline = NULL;
    main_source = NULL;
    main_queue = NULL;
    g_source_remove(main_bus_watch_id);
  }

  // Create elements
  main_pipeline = gst_pipeline_new("main_pipeline");
  main_source = gst_element_factory_make("v4l2src", "main_source");
  main_queue = gst_element_factory_make("queue", "main_queue");

  // Check that elements exists
  if (!main_pipeline) {
    g_error("Main pipeline could not be created.");
  }
  if (!main_source) {
    g_error("Main source could not be created.");
  }
  if (!main_queue) {
    g_error("Main queue could not be created.");
  }

  // Create caps
  main_source_caps = gst_caps_new_simple(
    media_type,
    "width", G_TYPE_INT, width,
    "height", G_TYPE_INT, height,
    "framerate", GST_TYPE_FRACTION, framerate, 1,
    NULL);

  // Add elements to bin and link
  gst_bin_add_many(GST_BIN(main_pipeline), main_source, main_queue, NULL);
  gst_element_link_filtered(main_source, main_queue, main_source_caps);

  // Add watch for EOS event
  bus = gst_pipeline_get_bus(GST_PIPELINE(main_pipeline));
  main_bus_watch_id = gst_bus_add_watch(bus, main_bus_cb, NULL);
  gst_object_unref(bus);
}

static void create_temp_pipeline() {
  GstBus *bus;

  g_message("Creating temp pipeline.");

  // Remove temp pipeline
  if (temp_pipeline) {
    gst_element_set_state(temp_pipeline, GST_STATE_NULL);
    gst_object_unref(temp_pipeline);
    temp_pipeline = NULL;
    temp_source = NULL;
    temp_queue = NULL;
    g_source_remove(temp_bus_watch_id);
  }

  // Create elements
  temp_pipeline = gst_pipeline_new("temp_pipeline");
  temp_source = gst_element_factory_make("fakesrc", "temp_source");
  temp_queue = gst_element_factory_make("queue", "temp_queue");

  // Check that elements exists
  if (!temp_pipeline) {
    g_error("Temp pipeline could not be created.");
  }
  if (!temp_source) {
    g_error("Temp source could not be created.");
  }
  if (!temp_queue) {
    g_error("Temp queue could not be created.");
  }

  // Add elements to bin and link
  gst_bin_add_many(GST_BIN(temp_pipeline), temp_source, temp_queue, NULL);
  gst_element_link(temp_source, temp_queue);

  // Add watch for EOS event
  bus = gst_pipeline_get_bus(GST_PIPELINE(temp_pipeline));
  temp_bus_watch_id = gst_bus_add_watch(bus, temp_bus_cb, NULL);
  gst_object_unref(bus);
}

static void create_bin(guint bin_num) {
  GstPad *pad;
  GstElement *bin, *queue, *parse, *muxer, *sink;

  // Create elements
  bin = gst_bin_new("bin");
  queue = gst_element_factory_make("queue", "queue");
  if (strcmp(media_type, "video/x-h264") == 0) {
    parse = gst_element_factory_make("h264parse", "parse");
  }
  else {
    parse = gst_element_factory_make("jpegparse", "parse");
  }
  muxer = gst_element_factory_make(muxer_name, "muxer");
  sink = gst_element_factory_make("filesink", "sink");

  // Check that elements exists
  if (!bin) {
    g_error("Bin could not be created.");
  }
  if (!queue) {
    g_error("Queue could not be created.");
  }
  if (!parse) {
    g_error("Parse could not be created.");
  }
  if (!muxer) {
    g_error("Muxer could not be created.");
  }
  if (!sink) {
    g_error("Sink could not be created.");
  }

  // Add elements to bin and link
  gst_bin_add_many(GST_BIN(bin), queue, parse, muxer, sink, NULL);
  gst_element_link_many(queue, parse, muxer, sink, NULL);

  // Create ghost pad for sink
  pad = gst_element_get_static_pad(queue, "sink");
  gst_element_add_pad(bin, gst_ghost_pad_new("sink", pad));
  gst_object_unref(GST_OBJECT(pad));

  // Copy pointers to correct globals
  if (bin_num == 1) {
    first_bin = bin;
    first_queue = queue;
    first_parse = parse;
    first_muxer = muxer;
    first_sink = sink;
  }
  else {
    second_bin = bin;
    second_queue = queue;
    second_parse = parse;
    second_muxer = muxer;
    second_sink = sink;
  }
}

static void set_stream_state(guint state) {
  FILE *file;
  stream_state = state;
  file = fopen(stream_state_path, "w");

  if (!file) {
    g_error("Write permission denied to stream state file: %s",
      stream_state_path);
  }

  fprintf(file, "%i", state);
  fclose(file);
}

static void set_sink_location(GstElement *sink) {
  gchar buffer[4096];
  gchar filename[4096];
  time_t rawtime;
  struct tm *timeinfo;

  // Set sink location using strftime
  time(&rawtime);
  timeinfo = localtime(&rawtime);
  strftime(buffer, 4096, output_path, timeinfo);

  // Format string for segment counter
  if (segment_counter > 9999) {
    segment_counter = 0;
  }
  sprintf(filename, buffer, segment_counter);
  segment_counter += 1;

  gst_element_set_state(sink, GST_STATE_NULL);
  g_object_set(G_OBJECT(sink), "location", filename, NULL);
  gst_element_set_state(sink, GST_STATE_PLAYING);
}

static void split_output(guint rebuild) {
  GstElement *current_bin, *next_bin, *next_muxer, *next_sink;

  g_message("Splitting output, active bin is %i.", active_bin);

  // Temp pipeline never received EOS could happen if disk locks up
  // or segment length doesn't leave enough time to finish writing last file
  if (gst_bin_get_by_name(GST_BIN(temp_pipeline), "bin") != NULL) {
    g_error("Temp pipeline failed to receive EOS.");
  }

  // Set next and current bin
  if (active_bin == 1) {
    active_bin = 2;
    current_bin = first_bin;
    next_bin = second_bin;
    next_muxer = second_muxer;
    next_sink = second_sink;
  }
  else {
    active_bin = 1;
    current_bin = second_bin;
    next_bin = first_bin;
    next_sink = first_sink;
  }

  // Update location
  if (rebuild) {
    set_sink_location(next_sink);
  }

  // Remove current bin from main pipeline
  gst_element_unlink(main_queue, current_bin);
  gst_object_ref(current_bin);
  gst_bin_remove(GST_BIN(main_pipeline), current_bin);

  // Add current bin to temp pipeline
  gst_element_set_state(temp_pipeline, GST_STATE_PLAYING);
  gst_bin_add(GST_BIN(temp_pipeline), current_bin);
  gst_object_unref(current_bin);
  gst_element_link(temp_queue, current_bin);

  // Send end of stream to temp pipeline
  gst_element_send_event(temp_queue, gst_event_new_eos());

  // If stream is not being rebuilt dont setup main pipeline
  if (!rebuild) {
    return;
  }

  // Stop main pipeline
  gst_element_set_state(main_pipeline, GST_STATE_NULL);

  // Sometimes video device will not close fast enough and will be busy
  // adjust sleep time to fix
  usleep(dev_delay);

  // Move next bin to main pipeline
  gst_bin_add(GST_BIN(main_pipeline), next_bin);
  gst_element_link(main_queue, next_bin);
  gst_element_set_state(main_pipeline, GST_STATE_PLAYING);
}

static gboolean split_output_cb(gpointer data) {
  if (stream_state) {
    split_output(1);
  }
  return TRUE;
}

static gboolean main_bus_cb(GstBus *bus, GstMessage *msg, gpointer data) {
  switch (GST_MESSAGE_TYPE(msg)) {
    case GST_MESSAGE_STREAM_START: {
      set_stream_state(1);
      break;
    }
    case GST_MESSAGE_EOS: {
      // Main pipeline should never receive EOS
      g_error("Received EOS on main pipeline.");
      break;
    }
    case GST_MESSAGE_ERROR: {
      GError *error = NULL;
      gchar *debug = NULL;
      gst_message_parse_error(msg, &error, &debug);

      if (error->domain == GST_RESOURCE_ERROR) {
        g_error("Resource error [%i]: %s", error->code, GST_RESOURCE_ERROR_FAILED, error->message);
      }
      else if (error->domain == GST_STREAM_ERROR) {
        // Device disconnected
        if (error->code == GST_RESOURCE_ERROR_FAILED &&
              access(dev_name, R_OK) != 0) {
          g_message("Video device disconnected, stopping stream...");

          // Free variables
          g_error_free(error);
          g_free(debug);

          // Set stream state and exit
          exit_app();
          break;
        }
        else {
          g_error("Stream error [%i]: %s", error->code, error->message);
        }
      }
      g_error("Unknown error [%i]: %s", error->code, error->message);
    }
  }

  return TRUE;
}

static gboolean temp_bus_cb(GstBus *bus, GstMessage *msg, gpointer data) {
  switch (GST_MESSAGE_TYPE(msg)) {
    case GST_MESSAGE_EOS: {
      g_message("Received EOS on temp pipeline, active bin %i.", active_bin);

      // If stream state is stopped exit was pending EOS
      if (!stream_state) {
        g_main_loop_quit(main_loop);
        break;
      }

      // Remove and recreate temp pipeline
      create_temp_pipeline();

      // Recreate bin
      if (active_bin == 1) {
        create_bin(2);
      }
      else {
        create_bin(1);
      }

      break;
    }
  }

  return TRUE;
}

int main(int argc, char *argv[]) {
  GError *error = NULL;
  GOptionContext *context;
  guint bus_watch_id;

  // Option entries
  GOptionEntry entries[] = {
    {
      "device", 'd', 0, G_OPTION_ARG_STRING, &dev_name,
      "Source device name", NULL
    },
    {
      "media-type", 't', 0, G_OPTION_ARG_STRING, &media_type,
      "Source media type", NULL
    },
    {
      "muxer-name", 'm', 0, G_OPTION_ARG_STRING, &muxer_name,
      "Gstreamer muxer name", NULL
    },
    {
      "output-path", 'o', 0, G_OPTION_ARG_STRING, &output_path,
      "Output path with strftime formating or %i to use segment counter.", NULL
    },
    {
      "dev-delay", 'b', 0, G_OPTION_ARG_INT, &dev_delay,
      "Device delay in microseconds", NULL
    },
    {
      "stream-state-path", 'p', 0, G_OPTION_ARG_STRING, &stream_state_path,
      "File path for stream state file", NULL
    },
    {
      "width", 'x', 0, G_OPTION_ARG_INT, &width,
      "Source width", NULL
    },
    {
      "height", 'y', 0, G_OPTION_ARG_INT, &height,
      "Source height", NULL
    },
    {
      "framerate", 'r', 0, G_OPTION_ARG_INT, &framerate,
      "Source framerate", NULL
    },
    {
      "segment-length", 's', 0, G_OPTION_ARG_INT, &segment_length,
      "Length in seconds of output files", NULL
    },
    {
      "segment-counter", 'c', 0, G_OPTION_ARG_INT, &segment_counter,
      "Starting number for segment counter. Used with %i in filename.", NULL
    },
    {NULL}
  };

  // Prase options
  context = g_option_context_new("- stream");
  g_option_context_add_main_entries(context, entries, NULL);
  g_option_context_add_group(context, gst_init_get_option_group());
  if (!g_option_context_parse(context, &argc, &argv, &error)) {
    g_error("Option parsing failed: %s", error->message);
  }

  // Check for required options
  if (!dev_name) {
    g_error("Device name is not specified.");
  }
  if (!media_type) {
    g_error("Media type is not specified.");
  }
  if (!muxer_name) {
    g_error("Muxer name is not specified.");
  }
  if (!output_path) {
    g_error("Output path is not specified.");
  }
  if (!stream_state_path) {
    g_error("Stream state path is not specified.");
  }
  if (!width) {
    g_error("Width is not specified.");
  }
  if (!height) {
    g_error("Height is not specified.");
  }
  if (!framerate) {
    g_error("Framerate is not specified.");
  }
  if (!segment_length) {
    g_error("Segment length is not specified.");
  }
  if (!strcmp(media_type, "video/x-h264") &&
      !strcmp(media_type, "image/jpeg")) {
    g_error("Media type must be video/x-h264 or image/jpeg.");
  }

  // Check access to output device
  if (access(dev_name, F_OK) != 0) {
    g_error("Device file not found %s", dev_name);
  }

  // Set stream state
  set_stream_state(0);

  // Create main loop
  main_loop = g_main_loop_new(NULL, FALSE);

  // Init gst
  gst_init(&argc, &argv);

  // Create pipelines and bins
  create_main_pipeline();
  create_temp_pipeline();
  create_bin(1);
  create_bin(2);

  // Setup first bin
  gst_bin_add(GST_BIN(main_pipeline), first_bin);
  gst_element_link(main_queue, first_bin);
  set_sink_location(first_sink);

  // Set device name
  g_object_set(G_OBJECT(main_source), "device", dev_name, NULL);

  // Add signal handlers
  signal(SIGINT, exit_app);
  signal(SIGTERM, exit_app);

  // Setup timeout to split output
  g_timeout_add_seconds(segment_length, split_output_cb, NULL);

  //gst_element_set_state(temp_pipeline, GST_STATE_PLAYING);
  g_message("Starting pipeline...");

  // Set state and run main loop
  gst_element_set_state(main_pipeline, GST_STATE_PLAYING);
  g_main_loop_run(main_loop);

  // // Remove main pipeline
  // gst_element_set_state(main_pipeline, GST_STATE_NULL);
  // gst_object_unref(main_pipeline);
  // main_pipeline = NULL;
  // g_source_remove(main_bus_watch_id);

  // // Remove temp pipeline
  // gst_element_set_state(temp_pipeline, GST_STATE_NULL);
  // gst_object_unref(temp_pipeline);
  // temp_pipeline = NULL;
  // g_source_remove(temp_bus_watch_id);

  g_message("Closing...");

  return 0;
}
